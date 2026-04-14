from .logging import configure_logging
from .subscriber import run


def main() -> None:
    configure_logging()
    run()


if __name__ == "__main__":
    main()
