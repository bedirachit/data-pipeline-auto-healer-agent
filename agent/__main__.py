"""Allow `python -m agent` to start the same CLI as `python -m agent.main`."""

from agent.main import main

if __name__ == "__main__":
    main()
