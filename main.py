"""
Minimal example demonstrating MindShell with Ollama (local LLM).

This example shows:
1. Initializing an Ollama LLM client
2. Creating a chat session
3. Querying the assistant
4. Using tools (filesystem, shell)
5. Exporting the session
"""

import asyncio
from pathlib import Path
from mind_shell.config.settings import LLMSettings, SessionSettings, ToolSettings, AgentSettings, UISettings, Settings
from mind_shell.core.session import SessionManager
from mind_shell.core.context import ContextManager
from mind_shell.core.tool_executor import ToolExecutor, ToolCallRequest
from mind_shell.llm.client import LLMClient
from mind_shell.tools import get_all_tools
from rich.console import Console

console = Console()


async def main():
    """
    Minimal example: Interactive assistant with Claude (Anthropic).
    
    Prerequisites:
        1. Get Anthropic API key: https://console.anthropic.com
        2. Set environment variable: export ANTHROPIC_API_KEY="sk-ant-..."
        3. Install anthropic SDK: pip install anthropic
    
    Optional (for Ollama fallback):
        - Install Ollama: https://ollama.ai
        - Pull a model: `ollama pull mistral`
        - Start Ollama: `ollama serve`
    """
    
    try:
        console.print("\n[bold cyan]🧠 MindShell with Claude (Anthropic)[/bold cyan]\n")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. Configure LLM (Anthropic - Claude)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        try:
            llm_settings = LLMSettings()
            # Use Anthropic Claude for native tool support
            llm_settings.provider = "anthropic"
            llm_settings.model = "claude-3-5-sonnet-20241022"  # Latest Claude with tool use
            llm_settings.fast_model = "claude-3-5-haiku-20241022"  # Fast model for quick tasks
            session_settings = SessionSettings()
            tool_settings = ToolSettings()
            agent_settings = AgentSettings()
            ui_settings = UISettings()

            settings = Settings(
                llm=llm_settings,
                session=session_settings,
                tools=tool_settings,
                agent=agent_settings,
                ui=ui_settings
            )
            
            console.print(f"[dim]LLM Provider:[/dim] {settings.llm.provider}")
            console.print(f"[dim]Model:[/dim] {settings.llm.model}")
            console.print(f"[dim]Base URL:[/dim] {settings.llm.base_url}")
            console.print(f"[dim]Tools:[/dim] {', '.join(settings.tools.enabled)}\n")
        except Exception as e:
            console.print(f"[red]❌ Configuration Error:[/red] {e}\n")
            return
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2. Initialize components
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        try:
            llm = LLMClient(settings=settings)
            session_manager = SessionManager(settings=settings)
            session = session_manager.new()
            context_manager = ContextManager(settings=settings)
            tools_list = get_all_tools(settings=settings)
            tool_executor = ToolExecutor(settings=settings, tools=tools_list)
            
            console.print(f"[green]✓[/green] Started session [bold]{session.id[:8]}[/bold]\n")
        except Exception as e:
            console.print(f"[red]❌ Initialization Error:[/red] {e}\n")
            return
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3. Example queries
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        queries = [
            "What files are in the current directory?",
            "Create a simple Python script that prints 'Hello from MindShell'",
            "Now run that script if it exists",
        ]
        
        for query_idx, query in enumerate(queries, 1):
            try:
                console.print(f"[bold blue]👤 You:[/bold blue] {query}\n")
                
                # Build context with the query
                try:
                    messages = context_manager.build(session=session, user_message=query)
                except Exception as e:
                    console.print(f"[red]❌ Context Error:[/red] Failed to build context: {e}\n")
                    continue
                
                # Get response from Ollama (async call)
                try:
                    response = await llm.chat(
                        messages=messages,
                        tools=tools_list
                    )
                except ConnectionError:
                    console.print(
                        "[red]❌ Connection Error:[/red] Cannot reach Ollama server.\n"
                        "[yellow]⚠️  Make sure:[/yellow]\n"
                        "  1. Ollama is installed (https://ollama.ai)\n"
                        "  2. Run 'ollama serve' in a terminal\n"
                        "  3. A model is downloaded: 'ollama pull mistral'\n"
                    )
                    return
                except TimeoutError:
                    console.print(
                        "[red]❌ Timeout Error:[/red] Ollama server is not responding.\n"
                        "[yellow]⚠️  Try:[/yellow]\n"
                        "  1. Restart Ollama: 'ollama serve'\n"
                        "  2. Check your internet connection\n"
                    )
                    continue
                except Exception as e:
                    console.print(f"[red]❌ LLM Error:[/red] {type(e).__name__}: {e}\n")
                    continue
                
                # Add assistant response to session
                try:
                    session.add_message(role="assistant", content=response.text)
                    console.print(f"[bold green]🤖 Assistant:[/bold green] {response.text}\n")
                    console.print("[dim]" + "─" * 80 + "[/dim]\n")
                except Exception as e:
                    console.print(f"[red]❌ Response Error:[/red] Failed to process response: {e}\n")
                    continue
                
                # Handle tool calls if any
                if response.tool_calls:
                    console.print("[dim]Executing tool calls...[/dim]\n")
                    
                    for tool_call in response.tool_calls:
                        try:
                            # Create ToolCallRequest
                            tool_call_req = ToolCallRequest(
                                name=tool_call.name,
                                input=tool_call.input,
                                id=tool_call.id
                            )
                            
                            # Execute with callbacks for monitoring
                            async def on_start(req, metrics, result=None):
                                console.print(f"[yellow]🔧 Executing:[/yellow] {req.name}")
                            
                            async def on_result(req, metrics, result):
                                console.print(f"[green]✓[/green] {metrics}")
                                if result.output:
                                    console.print(f"[dim]{result.output[:200]}{'...' if len(result.output) > 200 else ''}[/dim]")
                            
                            async def on_error(req, metrics, result):
                                console.print(f"[red]❌ {metrics}[/red]")
                                if result and result.error:
                                    console.print(f"[red]{result.error}[/red]")
                            
                            # Execute the tool
                            result = await tool_executor.execute(
                                tool_call_req,
                                on_start=on_start,
                                on_result=on_result,
                                on_error=on_error
                            )
                            
                            # Add to session
                            session.add_message(
                                role="tool",
                                content=str(result),
                                tool_name=tool_call.name,
                                tool_input=str(tool_call.input)
                            )
                            
                        except Exception as e:
                            console.print(f"[red]❌ Tool Error ({tool_call.name}):[/red] {type(e).__name__}: {e}\n")
                            continue
                    
                    # Print execution summary
                    console.print()
                    tool_executor.print_execution_summary()
                    console.print()
            
            except KeyboardInterrupt:
                console.print("\n[yellow]⚠️  Cancelled by user[/yellow]\n")
                break
            except Exception as e:
                console.print(f"[red]❌ Query Error (#{query_idx}):[/red] {type(e).__name__}: {e}\n")
                continue
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4. Save session
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        try:
            path: Path = session_manager.save(session)
            console.print(f"[green]✓[/green] Session saved to {path}\n")
        except Exception as e:
            console.print(f"[red]❌ Save Error:[/red] Failed to save session: {e}\n")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Interrupted by user[/yellow]\n")
    except Exception as e:
        console.print(f"[red]❌ Unexpected Error:[/red] {type(e).__name__}: {e}\n")
        import traceback
        console.print("[dim]Full traceback:[/dim]")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
