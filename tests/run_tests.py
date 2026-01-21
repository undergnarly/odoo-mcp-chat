#!/usr/bin/env python3
"""
Test runner script for Odoo AI Agent.

This script provides convenient ways to run different test suites.

Usage:
    python tests/run_tests.py              # Run all tests
    python tests/run_tests.py --quick      # Run quick tests (no real Odoo/LLM)
    python tests/run_tests.py --connection # Run only connection tests
    python tests/run_tests.py --agent      # Run only agent tests
    python tests/run_tests.py --verbose    # Run with verbose output
"""
import os
import sys
import argparse
import subprocess

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def check_dependencies():
    """Check if required test dependencies are installed."""
    missing = []

    try:
        import pytest
    except ImportError:
        missing.append("pytest")

    try:
        import pytest_asyncio
    except ImportError:
        missing.append("pytest-asyncio")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Install with: pip install pytest pytest-asyncio")
        return False

    return True


def check_env_vars():
    """Check and display environment variable status."""
    print("\n=== Environment Status ===")

    # Odoo configuration
    odoo_vars = ["ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD"]
    odoo_configured = all(os.environ.get(var) for var in odoo_vars)
    print(f"Odoo configured: {'Yes' if odoo_configured else 'No'}")
    if odoo_configured:
        print(f"  URL: {os.environ.get('ODOO_URL')}")
        print(f"  DB: {os.environ.get('ODOO_DB')}")

    # LLM configuration
    llm_configured = any([
        os.environ.get("ANTHROPIC_API_KEY"),
        os.environ.get("OPENAI_API_KEY"),
        os.environ.get("GOOGLE_API_KEY"),
    ])
    print(f"LLM configured: {'Yes' if llm_configured else 'No'}")
    if llm_configured:
        if os.environ.get("ANTHROPIC_API_KEY"):
            print("  Provider: Anthropic")
        elif os.environ.get("OPENAI_API_KEY"):
            print("  Provider: OpenAI")
        elif os.environ.get("GOOGLE_API_KEY"):
            print("  Provider: Google")

    print()
    return odoo_configured, llm_configured


def run_tests(args):
    """Run tests with specified options."""
    pytest_args = ["-v" if args.verbose else "-q"]

    # Add asyncio mode (for newer pytest-asyncio versions)
    # pytest_args.extend(["--asyncio-mode=auto"])

    # Select test files based on options
    if args.quick:
        # Run only unit tests that don't need real connections
        pytest_args.extend([
            "tests/test_config.py",
            "tests/test_prompts.py",
            "-k", "not real and not integration",
        ])
    elif args.connection:
        pytest_args.append("tests/test_odoo_connection.py")
    elif args.agent:
        pytest_args.append("tests/test_agent.py")
    elif args.discovery:
        pytest_args.append("tests/test_discovery.py")
    elif args.integration:
        pytest_args.append("tests/test_integration.py")
    else:
        # Run all tests
        pytest_args.append("tests/")

    # Add any extra pytest arguments
    if args.pytest_args:
        pytest_args.extend(args.pytest_args)

    print(f"Running: pytest {' '.join(pytest_args)}")
    print("=" * 50)

    # Run pytest
    return subprocess.call(["python", "-m", "pytest"] + pytest_args)


def main():
    parser = argparse.ArgumentParser(
        description="Run Odoo AI Agent tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tests/run_tests.py              # Run all tests
    python tests/run_tests.py --quick      # Quick tests (no external deps)
    python tests/run_tests.py --connection # Test Odoo connection
    python tests/run_tests.py --agent      # Test agent functionality
    python tests/run_tests.py -v           # Verbose output
    python tests/run_tests.py -- -k "test_client"  # Pass args to pytest
        """
    )

    parser.add_argument("--quick", "-q", action="store_true",
                        help="Run quick tests only (no real Odoo/LLM needed)")
    parser.add_argument("--connection", "-c", action="store_true",
                        help="Run only Odoo connection tests")
    parser.add_argument("--agent", "-a", action="store_true",
                        help="Run only agent tests")
    parser.add_argument("--discovery", "-d", action="store_true",
                        help="Run only discovery tests")
    parser.add_argument("--integration", "-i", action="store_true",
                        help="Run only integration tests")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose output")
    parser.add_argument("--check-env", action="store_true",
                        help="Only check environment, don't run tests")
    parser.add_argument("pytest_args", nargs="*",
                        help="Additional arguments to pass to pytest")

    args = parser.parse_args()

    # Check dependencies
    if not check_dependencies():
        return 1

    # Check environment
    odoo_ok, llm_ok = check_env_vars()

    if args.check_env:
        return 0 if (odoo_ok and llm_ok) else 1

    # Warn if running tests that need connections
    if not args.quick:
        if not odoo_ok:
            print("WARNING: Odoo not configured. Some tests will be skipped.")
            print("Set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD")
            print()
        if not llm_ok:
            print("WARNING: LLM not configured. Some tests will be skipped.")
            print("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY")
            print()

    # Run tests
    return run_tests(args)


if __name__ == "__main__":
    sys.exit(main())
