{ pkgs, lib, config, inputs, ... }:
let
  pkgs-playwright = import inputs.nixpkgs-playwright { system = pkgs.stdenv.system; };
  browsers = (builtins.fromJSON (builtins.readFile "${pkgs-playwright.playwright-driver}/browsers.json")).browsers;
  chromium-rev = (builtins.head (builtins.filter (x: x.name == "chromium") browsers)).revision;
in
{
  # https://devenv.sh/basics/
  env = {
    GREET = "devenv";
    PLAYWRIGHT_BROWSERS_PATH = "${pkgs-playwright.playwright.browsers}";
    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = true;
    PLAYWRIGHT_NODEJS_PATH = "${pkgs-playwright.nodejs}/bin/node";
    PLAYWRIGHT_LAUNCH_OPTIONS_EXECUTABLE_PATH = "${pkgs-playwright.playwright.browsers}/chromium-${chromium-rev}/chrome-linux/chrome";
  };

  # https://devenv.sh/packages/
  packages = [
    pkgs.git
    pkgs.curl
    pkgs.jq
    pkgs.yq
  ];

  # https://devenv.sh/languages/
  languages.javascript.enable = true;
  languages.javascript.bun.enable = true;
  languages.javascript.package = pkgs-playwright.nodejs;

  languages.python.enable = true;
  languages.python.uv.enable = true;
  languages.python.venv.enable = true;

  # https://devenv.sh/services/
  services.postgres = {
    enable = true;
    listen_addresses = "127.0.0.1";
    port = 5432;
    initialDatabases = [
      { name = "clothes_design_dev"; user = "postgres"; pass = "postgres"; }
      { name = "clothes_design_test"; user = "postgres"; pass = "postgres"; }
    ];
  };

  services.redis = {
    enable = true;
    port = 6379;
    bind = "127.0.0.1";
  };

  # https://devenv.sh/scripts/
  scripts.hello.exec = ''
    echo hello from $GREET
  '';

  scripts.check-playwright-versions.exec = ''
    playwrightNpmVersion=$(node -p "require('@playwright/test/package.json').version" 2>/dev/null)
    nixPlaywrightBaseVersion=$(echo "${pkgs-playwright.playwright.version}" | cut -d. -f1,2)
    npmPlaywrightBaseVersion=$(echo "$playwrightNpmVersion" | cut -d. -f1,2)

    echo "❄️ Playwright nix version: ${pkgs-playwright.playwright.version}"
    echo "📦 Playwright npm version: $playwrightNpmVersion"

    if [ "$nixPlaywrightBaseVersion" != "$npmPlaywrightBaseVersion" ]; then
        echo "❌ Playwright versions (major, minor) in nix ($nixPlaywrightBaseVersion in devenv.yaml) and npm ($npmPlaywrightBaseVersion in package.json) are not the same! Please adapt the configuration."
    else
        echo "✅ Playwright versions in nix and npm are the same"
    fi

    echo
    env | grep ^PLAYWRIGHT
  '';

  scripts.check-stack.exec = ''
    echo "=== Development Stack Verification ==="
    echo ""
    echo "Node.js:"
    node --version
    echo ""
    echo "Bun:"
    bun --version
    echo ""
    echo "Python:"
    python --version
    echo ""
    echo "PostgreSQL:"
    psql --version
    echo ""
    echo "Redis:"
    redis-cli --version
    echo ""
    echo "=== Services Status ==="
    redis-cli ping 2>/dev/null || echo "Redis: not running"
    psql -h 127.0.0.1 -U postgres -d clothes_design_dev -c "SELECT 1;" 2>/dev/null && echo "PostgreSQL: connected" || echo "PostgreSQL: not running"
  '';

  # https://devenv.sh/basics/
  enterShell = ''
    hello
    echo ""
    echo "✓ Development environment loaded"
    echo "Run 'check-stack' to verify all tools are available"
    echo "Run 'check-playwright-versions' to verify Playwright versions in nix and npm match"
  '';

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running environment tests"
    node --version | grep -E "v20\." && echo "✓ Node.js 20.x"
    bun --version && echo "✓ Bun"
    python --version | grep -E "3\.11" && echo "✓ Python 3.11"
    psql --version && echo "✓ PostgreSQL"
    redis-cli --version && echo "✓ Redis"
  '';

  dotenv.enable = true;
  # See full reference at https://devenv.sh/reference/options/
}
