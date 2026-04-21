"""
mind_shell/core/tool_executor.py — Tool execution orchestration.

Handles:
  - Parsing LLM tool calls
  - Executing tools with error handling
  - Formatting results back to context
  - Timeout protection
  - Execution logging and metrics
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable

from rich.console import Console
from rich.table import Table

from mind_shell.config.settings import Settings
from mind_shell.tools.base_tool import BaseTool, ToolResult


@dataclass
class ToolCallRequest:
    """Represents a tool call requested by the LLM."""
    name: str
    input: Dict[str, Any]
    id: Optional[str] = None


@dataclass
class ExecutionMetrics:
    """Metrics for tool execution."""
    tool_name: str
    success: bool
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    
    def finalize(self):
        """Record end time and calculate duration."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
    
    def __str__(self) -> str:
        status = "✅" if self.success else "❌"
        return f"{status} {self.tool_name} ({self.duration_ms:.0f}ms)"


class ToolExecutor:
    """
    Orchestrates tool execution with error handling, timeouts, and metrics.
    
    Usage:
        executor = ToolExecutor(settings, tools)
        result = await executor.execute(tool_call_request)
    """
    
    def __init__(self, settings: Settings, tools: List[BaseTool]):
        self.settings = settings
        self.tool_map = {t.name: t for t in tools}
        self.console = Console()
        self.execution_history: List[ExecutionMetrics] = []
        
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self.tool_map.get(name)
    
    def list_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.tool_map.keys())
    
    async def execute(
        self,
        tool_call: ToolCallRequest,
        on_start: Optional[Callable] = None,
        on_result: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> ToolResult:
        """
        Execute a single tool call with error handling and metrics.
        
        Args:
            tool_call: The tool call to execute
            on_start: Callback when execution starts
            on_result: Callback when execution succeeds
            on_error: Callback when execution fails
            
        Returns:
            ToolResult with output, success status, and error if applicable
        """
        metrics = ExecutionMetrics(tool_name=tool_call.name, success=False)
        
        # Callback: execution started
        if on_start:
            await self._run_callback(on_start, tool_call, metrics)
        
        # Validate tool exists
        tool = self.get_tool(tool_call.name)
        if not tool:
            error_msg = f"Unknown tool: '{tool_call.name}'. Available: {', '.join(self.list_tools())}"
            result = ToolResult(
                output="",
                success=False,
                error=error_msg
            )
            metrics.error = error_msg
            metrics.success = False
            metrics.finalize()
            self.execution_history.append(metrics)
            
            if on_error:
                await self._run_callback(on_error, tool_call, metrics, result)
            return result
        
        # Validate input schema
        validation_error = self._validate_input(tool, tool_call.input)
        if validation_error:
            result = ToolResult(
                output="",
                success=False,
                error=f"Invalid input: {validation_error}"
            )
            metrics.error = validation_error
            metrics.success = False
            metrics.finalize()
            self.execution_history.append(metrics)
            
            if on_error:
                await self._run_callback(on_error, tool_call, metrics, result)
            return result
        
        # Execute with timeout
        try:
            timeout = self.settings.tools.shell_timeout
            result = await asyncio.wait_for(
                tool.execute(tool_call.input),
                timeout=timeout
            )
            
            metrics.success = True
            metrics.finalize()
            self.execution_history.append(metrics)
            
            if on_result:
                await self._run_callback(on_result, tool_call, metrics, result)
            
            return result
            
        except asyncio.TimeoutError:
            error_msg = f"Tool execution timeout after {self.settings.tools.shell_timeout}s"
            result = ToolResult(
                output="",
                success=False,
                error=error_msg
            )
            metrics.error = error_msg
            metrics.success = False
            metrics.finalize()
            self.execution_history.append(metrics)
            
            if on_error:
                await self._run_callback(on_error, tool_call, metrics, result)
            return result
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            result = ToolResult(
                output="",
                success=False,
                error=error_msg
            )
            metrics.error = error_msg
            metrics.success = False
            metrics.finalize()
            self.execution_history.append(metrics)
            
            if on_error:
                await self._run_callback(on_error, tool_call, metrics, result)
            return result
    
    async def execute_many(
        self,
        tool_calls: List[ToolCallRequest],
        parallel: bool = False,
        on_start: Optional[Callable] = None,
        on_result: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> List[ToolResult]:
        """
        Execute multiple tool calls.
        
        Args:
            tool_calls: List of tool calls to execute
            parallel: If True, execute all in parallel; if False, execute sequentially
            on_start: Callback when each execution starts
            on_result: Callback when each execution succeeds
            on_error: Callback when each execution fails
            
        Returns:
            List of ToolResults in order matching tool_calls
        """
        if not tool_calls:
            return []
        
        if parallel:
            # Execute all in parallel
            tasks = [
                self.execute(tc, on_start, on_result, on_error)
                for tc in tool_calls
            ]
            return await asyncio.gather(*tasks)
        else:
            # Execute sequentially
            results = []
            for tc in tool_calls:
                result = await self.execute(tc, on_start, on_result, on_error)
                results.append(result)
            return results
    
    def _validate_input(self, tool: BaseTool, tool_input: Dict[str, Any]) -> Optional[str]:
        """
        Validate tool input against the tool's schema.
        
        Returns:
            Error message if validation fails, None if valid
        """
        if not hasattr(tool, 'input_schema') or not tool.input_schema:
            return None  # No schema to validate against
        
        schema = tool.input_schema
        
        # Basic JSON Schema validation
        if 'properties' in schema:
            required = schema.get('required', [])
            
            # Check required fields
            for field_name in required:
                if field_name not in tool_input:
                    return f"Missing required field: '{field_name}'"
            
            # Validate field types
            for field_name, value in tool_input.items():
                if field_name not in schema['properties']:
                    return f"Unknown field: '{field_name}'"
                
                prop_schema = schema['properties'][field_name]
                expected_type = prop_schema.get('type', 'string')
                
                # Simple type checking
                if not self._type_matches(value, expected_type):
                    return f"Field '{field_name}' should be {expected_type}, got {type(value).__name__}"
        
        return None
    
    def _type_matches(self, value: Any, expected_type: str) -> bool:
        """Check if a value matches an expected JSON schema type."""
        type_map = {
            'string': str,
            'number': (int, float),
            'integer': int,
            'boolean': bool,
            'array': list,
            'object': dict,
            'null': type(None),
        }
        
        expected = type_map.get(expected_type)
        if expected is None:
            return True  # Unknown type, assume valid
        
        return isinstance(value, expected)
    
    async def _run_callback(
        self,
        callback: Callable,
        tool_call: ToolCallRequest,
        metrics: ExecutionMetrics,
        result: Optional[ToolResult] = None,
    ):
        """Run a callback, handling both sync and async callbacks."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(tool_call, metrics, result)
            else:
                callback(tool_call, metrics, result)
        except Exception as e:
            # Log callback errors but don't fail
            self.console.print(f"[yellow]⚠️  Callback error:[/yellow] {e}")
    
    def get_execution_metrics(self) -> List[ExecutionMetrics]:
        """Get all execution metrics."""
        return self.execution_history.copy()
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of tool executions."""
        if not self.execution_history:
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "total_duration_ms": 0.0,
                "by_tool": {}
            }
        
        by_tool = {}
        total_duration = 0.0
        successful = 0
        failed = 0
        
        for metric in self.execution_history:
            total_duration += metric.duration_ms
            
            if metric.success:
                successful += 1
            else:
                failed += 1
            
            if metric.tool_name not in by_tool:
                by_tool[metric.tool_name] = {
                    "count": 0,
                    "successful": 0,
                    "failed": 0,
                    "total_duration_ms": 0.0
                }
            
            by_tool[metric.tool_name]["count"] += 1
            by_tool[metric.tool_name]["total_duration_ms"] += metric.duration_ms
            
            if metric.success:
                by_tool[metric.tool_name]["successful"] += 1
            else:
                by_tool[metric.tool_name]["failed"] += 1
        
        return {
            "total": len(self.execution_history),
            "successful": successful,
            "failed": failed,
            "total_duration_ms": total_duration,
            "by_tool": by_tool
        }
    
    def print_execution_summary(self):
        """Print a formatted execution summary to console."""
        summary = self.get_execution_summary()
        
        if summary["total"] == 0:
            self.console.print("[dim]No tool executions yet[/dim]")
            return
        
        # Create summary table
        table = Table(title="Tool Execution Summary")
        table.add_column("Tool", style="cyan")
        table.add_column("Calls", justify="right")
        table.add_column("Successful", justify="right", style="green")
        table.add_column("Failed", justify="right", style="red")
        table.add_column("Duration (ms)", justify="right")
        
        for tool_name, stats in summary["by_tool"].items():
            table.add_row(
                tool_name,
                str(stats["count"]),
                str(stats["successful"]),
                str(stats["failed"]),
                f"{stats['total_duration_ms']:.0f}"
            )
        
        # Add totals row
        table.add_row(
            "[bold]Total[/bold]",
            str(summary["total"]),
            f"[green]{summary['successful']}[/green]",
            f"[red]{summary['failed']}[/red]",
            f"{summary['total_duration_ms']:.0f}",
        )
        
        self.console.print(table)
