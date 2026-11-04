# Serial protocol

Legacy baseline: Mega Serial1 D18 TX / D19 RX; ESP32 GPIO41 RX / GPIO42 TX; 9600 baud, 8N1; newline terminates a message. TX/RX are crossed and grounds shared. Convert Mega's 5V TX level before ESP32 RX.

Mega sends `SCAN\n` only after the tracked bottle reaches fixed recognition station 4 and the settling time expires. ESP32 returns one of:

| Reply | Meaning |
|---|---|
| RESULT,0 | PetBottle |
| RESULT,1 | AluCan |
| RESULT,2 | Other |
| RESULT,-1 | Low confidence, capture failure, or inference failure |

The model's Other class is valid; it is not the error -1. Mega accepts a result only during WAIT_AI. The old targets are -30 / 0 / +30 for the old chute. The new controller must map these same categories to verified bin indexes and output positions, not reuse old angles.

The protocol has no request ID. The old real-AI controller locks after a 20-second result timeout and requires both boards reset, bottle cleared and references re-established. Future protocol extensions must specify message formats, units, request IDs and both endpoints before implementation.
