#!/usr/bin/env python3
"""
Quick validation script to verify MindShell Tool Executor integration.

Run this to check:
1. All imports work
2. Components are properly connected
3. Configuration is valid
"""

import sys
from pathlib import Path

def check_imports():
    """Verify all imports work correctly."""
    print("🔍 Checking imports...")
    try:
        from mind_shell.config.settings import Settings
        from mind_shell.core.tool_executor import ToolExecutor, ToolCallRequest
        from mind_shell.llm.client import LLMClient
        from mind_shell.tools import get_all_tools
        print("  ✓ All imports successful\n")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}\n")
        return False


def check_tool_executor():
    """Verify ToolExecutor is properly implemented."""
    print("🔍 Checking ToolExecutor class...")
    try:
        from mind_shell.core.tool_executor import ToolExecutor, ToolCallRequest, ExecutionMetrics
        
        # Check required methods
        required_methods = [
            'execute', 'execute_many', 'get_execution_metrics',
            'get_execution_summary', 'print_execution_summary',
            '_validate_input', '_type_matches'
        ]
        
        for method in required_methods:
            if not hasattr(ToolExecutor, method):
                print(f"  ✗ Missing method: {method}\n")
                return False
        
        print("  ✓ ToolExecutor has all required methods\n")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        return False


def check_settings():
    """Verify settings are correct."""
    print("🔍 Checking settings...")
    try:
        from mind_shell.config.settings import Settings, LLMSettings
        
        settings = Settings()
        
        # Check LLM defaults
        if settings.llm.provider != "anthropic":
            print(f"  ⚠ LLM provider: {settings.llm.provider} (expected: anthropic)\n")
            return False
        
        if "claude" not in settings.llm.model.lower():
            print(f"  ⚠ LLM model: {settings.llm.model} (expected: claude-*)\n")
            return False
        
        print(f"  ✓ LLM Provider: {settings.llm.provider}")
        print(f"  ✓ LLM Model: {settings.llm.model}")
        print(f"  ✓ Tools enabled: {', '.join(settings.tools.enabled[:3])}...\n")
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        return False


def check_main_py():
    """Verify main.py has been updated."""
    print("🔍 Checking main.py integration...")
    try:
        main_py = Path("main.py")
        if not main_py.exists():
            print("  ✗ main.py not found\n")
            return False
        
        content = main_py.read_text()
        
        checks = {
            "ToolExecutor import": "from mind_shell.core.tool_executor import ToolExecutor",
            "ToolCallRequest import": "from mind_shell.core.tool_executor import ToolCallRequest",
            "Anthropic provider": 'llm_settings.provider = "anthropic"',
            "Claude 3.5 Sonnet": "claude-3-5-sonnet",
            "tool_executor instantiation": "tool_executor = ToolExecutor",
            "ToolExecutor usage": "await tool_executor.execute(",
        }
        
        for check_name, check_string in checks.items():
            if check_string not in content:
                print(f"  ✗ {check_name}: NOT FOUND")
                return False
            print(f"  ✓ {check_name}")
        
        print()
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        return False


def main():
    """Run all checks."""
    print("\n" + "="*60)
    print("MindShell - Integration Verification")
    print("="*60 + "\n")
    
    checks = [
        check_imports,
        check_tool_executor,
        check_settings,
        check_main_py,
    ]
    
    results = [check() for check in checks]
    
    print("="*60)
    if all(results):
        print("✅ All checks passed! Ready to use.\n")
        print("📋 Next Steps:")
        print("   1. Set ANTHROPIC_API_KEY environment variable")
        print("        $env:ANTHROPIC_API_KEY='sk-ant-YOUR_KEY'")
        print("   2. Run: python main.py")
        print("   3. Watch tool execution with metrics!\n")
        return 0
    else:
        print("❌ Some checks failed. See above for details.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
