/*
 * adpcm.h — Header for ADPCM benchmark
 */
#ifndef ADPCM_H
#define ADPCM_H

int  adpcm_encode(int pcm_sample);
int  adpcm_decode(int nibble);
void adpcm_reset(void);

#endif /* ADPCM_H */
