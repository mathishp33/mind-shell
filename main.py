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
from mind_shell.llm.client import LLMClient
from mind_shell.tools import get_all_tools
from rich.console import Console

console = Console()


async def main():
    """
    Minimal example: Interactive assistant with Ollama.
    
    Prerequisites:
        1. Install Ollama: https://ollama.ai
        2. Pull a model: `ollama pull mistral` (or llama2, neural-chat, etc.)
        3. Start Ollama: `ollama serve` (runs on localhost:11434)
    """
    
    try:
        console.print("\n[bold cyan]🧠 MindShell with Ollama[/bold cyan]\n")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1. Configure LLM (Ollama)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        try:
            llm_settings = LLMSettings()
            llm_settings.provider = "ollama"
            llm_settings.model = "mistral"
            llm_settings.base_url = "http://localhost:11434"
            llm_settings.fast_model = "mistral"
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
                    for tool_call in response.tool_calls:
                        tool_name = tool_call.name
                        tool = next((t for t in tools_list if t.name == tool_name), None)
                        
                        if not tool:
                            console.print(f"[red]❌ Unknown tool:[/red] {tool_name}\n")
                            continue
                        
                        try:
                            result = await tool.execute(tool_call.input)
                            console.print(f"[yellow]🔧 {tool_name}:[/yellow] {result}\n")
                            session.add_message(
                                role="tool",
                                content=str(result),
                                tool_name=tool_name,
                                tool_input=str(tool_call.input)
                            )
                        except PermissionError:
                            console.print(
                                f"[red]❌ Permission Denied:[/red] Tool '{tool_name}' cannot access required resources.\n"
                            )
                        except TimeoutError:
                            console.print(
                                f"[red]❌ Timeout:[/red] Tool '{tool_name}' took too long to execute.\n"
                            )
                        except Exception as e:
                            console.print(f"[red]❌ Tool Error ({tool_name}):[/red] {type(e).__name__}: {e}\n")
            
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
