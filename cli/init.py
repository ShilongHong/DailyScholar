from core.bootstrap import run_init_wizard


def main() -> None:
    target = run_init_wizard()
    print(f"初始化完成: {target}")


if __name__ == "__main__":
    main()
