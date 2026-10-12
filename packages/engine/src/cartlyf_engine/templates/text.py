def count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"
