import nox

# TODO: load supported versions from pyproject.toml
# TODO: support older python versions
PYTHON_VERSIONS = ["3.9", "3.10", "3.11", "3.12", "3.13", "3.14"]


@nox.session(name="ruff", python=PYTHON_VERSIONS, reuse_venv=True)
def run_ruff(session: nox.Session) -> None:
    session.run("poetry", "install", "--all-extras", external=True)
    session.run("poetry", "run", "ruff", "check", external=True)
    session.run("poetry", "run", "ruff", "format", "--check", external=True)


@nox.session(name="mypy", python=PYTHON_VERSIONS, reuse_venv=True)
def run_mypy(session: nox.Session) -> None:
    session.run("poetry", "install", "--all-extras", external=True)
    session.run("poetry", "run", "mypy", external=True)


@nox.session(name="pytest", python=PYTHON_VERSIONS, reuse_venv=True)
def run_pytest(session: nox.Session) -> None:
    session.run("poetry", "install", "--all-extras", external=True)
    session.run("poetry", "run", "pytest", "--cov-report=xml", external=True)
