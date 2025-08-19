# pseudocode_to_awl

This repository contains a small Python script that converts simple pseudo code / structured text to **AWL** instructions (the Siemens S7 PLC assembly language).

## Usage

Provide pseudocode lines on standard input:

```bash
python transpile.py <<'EOF'
int Count
Result = 1 + 2
DoorOpen = SensorA AND NOT SensorB
EOF
```

Output:

```
VAR Count : INT := 0;

L     1
L     2
+I
T     Result

A     SensorA
UN    SensorB
=     DoorOpen
```

Each input line is translated independently and blank lines are inserted between statements. Comments starting with `//` are ignored.

You can also translate a single line by passing it as an argument:

```bash
python transpile.py "Result = 1 + 2"
```

## VS Code

An experimental extension lives under `vscode-extension`. Open this folder in VS Code and press `F5` to launch a development instance. Files with the `.pseudo` extension use the custom pseudocode language: when you press **Enter** at the end of a line, the line is replaced with its AWL translation by calling `transpile.py`.
