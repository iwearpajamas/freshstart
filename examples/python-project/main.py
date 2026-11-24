"""Example Python project used by the Freshstart quick start.

The configuration file at ``.freshstart.yml`` runs a couple of setup steps
when tested in a clean container.
"""


def greet(name: str = "Freshstart") -> str:
    """Return a friendly greeting message."""
    return f"Hello, {name}!"


if __name__ == "__main__":
    print(greet())
