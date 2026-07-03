import typer

VERSION = "0.1.0"

app = typer.Typer()


@app.callback()
def _main() -> None:
    pass


@app.command()
def version() -> None:
    typer.echo(VERSION)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
