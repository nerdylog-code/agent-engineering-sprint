import sys

from agent_lab.mcp_server import MCPServer

if __name__ == "__main__":
    MCPServer().serve(sys.stdin, sys.stdout)
