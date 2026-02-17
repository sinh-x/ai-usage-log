{ pkgs, lib, config, inputs, ... }:

{
  name = "ai-usage-log";

  env = {
    GREET = "AI Usage Log MCP Server Development Environment";
    POETRY_VIRTUALENVS_IN_PROJECT = "true";
    POETRY_VIRTUALENVS_CREATE = "true";
  };

  packages = with pkgs; [
    git
    openssh
  ];

  languages.python = {
    enable = true;
    version = "3.12";

    poetry = {
      enable = true;
      activate.enable = true;
      install = {
        enable = true;
        installRootPackage = true;
        compile = false;
        groups = [ ];
        verbosity = "more";
      };
    };
  };

  scripts = {
    serve.exec = ''
      echo "Starting AI Usage Log MCP Server (stdio)..."
      ai-usage-log
    '';

    check.exec = ''
      echo "Checking Python compilation..."
      python -m py_compile src/ai_usage_log/server.py
      echo "OK"
    '';

    test-startup.exec = ''
      echo "Testing server startup (5s timeout)..."
      timeout 5s ai-usage-log || true
    '';
  };

  enterTest = ''
    echo "Running verification tests..."
    python --version
    poetry --version
  '';

  git-hooks.hooks = {
    nixpkgs-fmt.enable = true;
    ruff.enable = true;
  };

  dotenv.enable = true;

  enterShell = ''
    echo ""
    echo "$GREET"
    echo ""
    echo "Available commands:"
    echo "  serve          - Run MCP server (stdio transport)"
    echo "  check          - Verify Python compilation"
    echo "  test-startup   - Test server startup with timeout"
    echo ""
    echo "Python: $(python --version)"
    echo "Poetry: $(poetry --version)"
    echo ""
  '';
}
