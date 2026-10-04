def main():
    while True:
        print("\n=== Select Mode ===")
        print("1. GUI Mode")
        print("2. TUI Mode")
        print("3. Exit")
        choice = input("Choose an option: ").strip().lower()
        if choice == "1":
            from gui import MathQuizApp
            MathQuizApp().mainloop()
        if choice == "2":
            from tui import MathQuizTUI
            MathQuizTUI().run()
        if choice == "3":
            from engine import clear
            clear()
            print("Exiting the program.")
            break

if __file__ == "__main__":
    main()