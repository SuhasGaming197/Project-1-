```c
#include "adpcm.h"
#include <stdio.h>

void test_adpcm() {
    int test_cases[] = {
        0, 32767, -32768,      // Boundary values
        -1, 1,                 // Edge test values
        16384, 8192, 4096,     // Power-of-two values
        -16384, -8192, -4096,  // Negative power-of-two values
        0x0000, 0xFFFF,        // All-zeros and all-ones bit patterns
        32767, -32768, 32767, -32768, // Alternating max/min values
        32767, 32767, -32768, -32768, // Repeated identical inputs
        1, 0, -1,              // Transition tests around zero
        2, 4, 8, 16,           // Powers of two
        3, 5, 9, 15,           // Nibbles that cover all branches
        6, 10, 14, 12, 11,     // Test various states through addition and subtraction
        -2, -4, -8, -16,       // Negative powers of two
        256, -256, 512, -512,  // Larger steps
        12345, -12345,         // Mid-range values
        32766, -32767,         // Values near limits
        -32766, 32768,         // Out of range values
        137, 101,              // Random samples to cover different branches
    };

    int i;
    int encoded;
    int decoded;

    // Reset the ADPCM state before testing
    adpcm_reset();

    for (i = 0; i < sizeof(test_cases) / sizeof(test_cases[0]); i++) {
        // Test Encoding
        encoded = adpcm_encode(test_cases[i]);
        printf("Encoded PCM sample %d to ADPCM nibble: %d\n", test_cases[i], encoded);
        // Test Decoding
        decoded = adpcm_decode(encoded);
        printf("Decoded ADPCM nibble %d back to PCM sample: %d\n", encoded, decoded);
    }

    // Test reset
    adpcm_reset();
    printf("ADPCM state reset.\n");
}

int main() {
    test_adpcm();
    return 0;
}
```