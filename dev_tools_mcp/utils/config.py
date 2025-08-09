"""Service configuration definition."""

from pydantic_settings import BaseSettings


class ServiceConfig(BaseSettings):
    """
    Defines the configuration for the MCP server, loaded from environment
    variables or a .env file.
    """

    # MCP Server transport mechanism (e.g., "stdio", "sse", "streamable-http")
    MCP_TRANSPORT: str = "stdio"
    # Host for the MCP server to bind to. Defaults to 0.0.0.0 for accessibility.
    MCP_HOST: str = "0.0.0.0"
    # Port for the MCP server to listen on.
    MCP_PORT: int = 8660

    class Config:
        """Pydantic configuration settings."""

        # We do not specify env_file here.
        # Environment loading is handled explicitly in main.py via load_dotenv
        # to ensure the correct .env file is used.
        extra = "ignore"
