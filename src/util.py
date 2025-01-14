from pydantic import ValidationError


def format_validation_error(e: ValidationError, source: str = None, indentation: str = "    ") -> str:
    root_message = f"{e.error_count()} errors" if e.error_count() > 1 else "Error"
    root_message += f" while parsing {e.title}"
    if source:
        root_message += f" from {source}"
    root_message += ":"

    error_messages = [root_message]
    for error in e.errors():
        is_root = len(error["loc"]) == 0
        message = indentation

        if not is_root:
            message += " -> ".join(map(str, error["loc"])) + ": "

        message += error['msg']

        if not is_root:
            value = error.get("input")
            if value:
                message += f" (given: {value})"

        error_messages.append(message)
    return "\n".join(error_messages)
