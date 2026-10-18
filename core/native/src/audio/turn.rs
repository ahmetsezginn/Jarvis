//! Bounded turn endpointing. Input is 100 ms of PCM plus a speech-model decision.
use std::collections::VecDeque;

#[derive(Default)]
pub struct TurnDetector {
    pre: VecDeque<f32>,
    pub samples: Vec<f32>,
    onset: usize,
    silence: usize,
    pub listening: bool,
    pub complete: bool,
    pub truncated: bool,
}

impl TurnDetector {
    pub fn push(&mut self, frame: &[f32], speech: bool) {
        if self.complete {
            return;
        }
        if !self.listening {
            self.pre.extend(frame);
            while self.pre.len() > 12800 {
                self.pre.pop_front();
            }
            self.onset = if speech { self.onset + 1 } else { 0 };
            if self.onset >= 2 {
                self.listening = true;
                self.samples = self.pre.drain(..).collect();
            }
            return;
        }
        self.samples.extend_from_slice(frame);
        self.silence = if speech { 0 } else { self.silence + 1 };
        self.complete = self.silence >= 9;
        if self.samples.len() >= 16000 * 30 {
            self.samples.truncate(16000 * 30);
            self.complete = true;
            self.truncated = true;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    const FRAME: [f32; 1600] = [0.1; 1600];
    #[test]
    fn silence_and_brief_noise_never_form_a_turn_and_memory_is_bounded() {
        let mut turn = TurnDetector::default();
        for i in 0..10000 {
            turn.push(&FRAME, i % 20 < 1);
        }
        assert!(!turn.listening && !turn.complete && turn.samples.is_empty());
        assert_eq!(turn.pre.len(), 12800);
    }
    #[test]
    fn onset_keeps_preroll_pauses_do_not_split_and_silence_completes_once() {
        let mut turn = TurnDetector::default();
        for _ in 0..8 {
            turn.push(&FRAME, false);
        }
        for _ in 0..2 {
            turn.push(&FRAME, true);
        }
        assert!(turn.listening);
        assert_eq!(turn.samples.len(), 12800);
        for _ in 0..8 {
            turn.push(&FRAME, false);
        }
        assert!(!turn.complete);
        turn.push(&FRAME, true);
        for _ in 0..9 {
            turn.push(&FRAME, false);
        }
        assert!(turn.complete && !turn.truncated);
        let length = turn.samples.len();
        turn.push(&FRAME, true);
        assert_eq!(length, turn.samples.len());
    }
    #[test]
    fn continuous_speech_is_bounded_and_marked_incomplete() {
        let mut turn = TurnDetector::default();
        for _ in 0..400 {
            turn.push(&FRAME, true);
        }
        assert!(turn.complete && turn.truncated);
        assert_eq!(turn.samples.len(), 16000 * 30);
    }
}
