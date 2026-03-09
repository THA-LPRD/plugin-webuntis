import sys

from loguru import logger
from pydantic import ValidationError

from app.settings import _Settings

try:
    Settings = _Settings()  # type: ignore[call-arg]
except ValidationError as e:
    print("\n❌ Configuration Error\n")
    print("The following settings are invalid:\n")

    for error in e.errors():
        field_name = error["loc"][0] if error["loc"] else "unknown"
        error_type = error["type"]

        env_var = str(field_name).upper()

        print(f"  • {field_name}:")
        print(f"    Environment variable: {env_var}")

        if error_type == "missing":
            print("    Error: This field is required but not set")
        else:
            if "input" in error and not isinstance(error["input"], dict):
                print(f"    Provided value: '{error['input']}'")
            print(f"    Error: {error['msg']}")

        print()

    print("Please check your .env file or environment variables and try again.")
    sys.exit(1)


logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YY-MM-DD HH:mm:ss.SSS}</green> - <level>{level}</level> - <cyan>{extra[classname]}</cyan> - <level>{message}</level>",
    level=Settings.log_level.upper(),
    colorize=True,
)
