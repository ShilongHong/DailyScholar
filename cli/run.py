import uvicorn


def main() -> None:
    uvicorn.run("app:app", host="0.0.0.0", port=20001, reload=False)


if __name__ == "__main__":
    main()
