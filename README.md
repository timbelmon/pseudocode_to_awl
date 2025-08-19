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
