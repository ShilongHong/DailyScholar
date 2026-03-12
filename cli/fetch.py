from app import run_fetch_papers


def main() -> None:
    result = run_fetch_papers()
    print(result)


if __name__ == "__main__":
    main()
