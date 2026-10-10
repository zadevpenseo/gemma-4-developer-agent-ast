# Deterministic AST-Guided Fault Localization for 4-Bit Quantized Developer Agents

**Kaggle Track**: The Gemma 4 Developer Agent Competition (Paper Track)  
**Author**: Muhammad Khoiruzzadittaqwa  
**Affiliation**: Institut Al Bahjah, Cirebon, Indonesia (Email: muhzadit@gmail.com)  
**Code Repository**: [github.com/zadevpenseo/gemma-4-developer-agent-ast](https://github.com/zadevpenseo/gemma-4-developer-agent-ast)  
**Manuscript PDF**: [`manuscript.pdf`](https://github.com/zadevpenseo/gemma-4-developer-agent-ast/blob/main/paper/manuscript.pdf)  
**Interactive Web Simulator**: [Live Demo on GitHub Pages](https://zadevpenseo.github.io/gemma-4-developer-agent-ast/)

---

## The Core Problem: Why Quantized Agents Break on Big Files

When building software repair agents, the instinct is simple: give the model the whole file so it has full context. On full-precision frontier models in the cloud, that works well enough. But the Gemma 4 competition requires running a 4-bit quantized 31B model locally on a single Kaggle L4 GPU within a strict 12-hour budget.

Here is what happens when you feed a 3,000-line Python file to a 4-bit model: it fails, and it fails predictably. 

The issue is not that the model cannot read Python syntax. The issue is attention dilution. Under 4-bit weight quantization (W4A16), every matrix multiplication introduces slight rounding noise. When you stretch the sequence across 4,000 or 8,000 tokens, that noise accumulates across the dot products. The attention logits flatten out. Instead of placing sharp, focused attention on the single function where an exception occurred, the model scatters its attention across hundreds of irrelevant lines. 

The symptom is familiar to anyone who has debugged local agents: the model misidentifies innocent utility functions as the bug, hallucinates imaginary method arguments, or attempts massive 200-line rewrites that break adjacent tests.

---

## The Intuition and the Math

We can see this breakdown directly in the attention mechanics. Multi-head self-attention computes:

$$A_h = \text{softmax}\left(\frac{Q_h K_h^T}{\sqrt{d_k}}\right)$$

Under 4-bit quantization, weight matrices $W_Q$ and $W_K$ contain quantization errors $E_Q$ and $E_K$. The perturbation in logits grows with the sequence length $N$:

$$\text{Var}(\Delta S_h) \propto N \cdot \sigma_E^2$$

As context grows, the noise variance overwhelms the true signal. If we track the normalized Shannon entropy of the attention distribution:

$$H(A_h(i, :)) = -\frac{1}{\log N} \sum_{j=1}^N A_h(i, j) \log A_h(i, j)$$

we find that above 3,500 tokens, entropy approaches 1.0. That means the attention weights behave almost like random uniform noise. The model literally cannot focus.

The takeaway was clear: to fix 4-bit agent accuracy, we did not need a bigger prompt. We needed to aggressively shrink the input. If we keep the context budget strictly under 1,500 tokens, the error variance remains tightly bounded, entropy stays low ($H < 0.35$), and the model recovers its sharp discriminatory power.

---

## How We Solved It: A 3-Stage Declarative Pipeline

Rather than feeding raw source code, we built an Abstract Syntax Tree (AST) skeletonizer into the Google Agent Development Kit (ADK) harness. 

Our pipeline separates fault localization from code editing across three dedicated sub-agents:

```text
Issue Description & Repository Root
               │
               ▼
   [Localizer Sub-Agent]
   Tree-sitter AST Skeleton Search (< 1,500 tokens)
               │
               ▼
   [Synthesizer Sub-Agent]
   Minimal Unified Diff Authoring (< 2,048 tokens)
               │
               ▼
   [Verifier Sub-Agent]
   Syntax Integrity & 80-Line Ceiling Audit (< 512 tokens)
               │
               ▼
   Deterministic Git Patch Application
```

### Stage 1: The Localizer (AST Skeletons, Not Full Text)
The Localizer never reads raw function bodies during its search. Instead, an AST parser extracts an architectural outline of each file: class definitions, decorated method signatures, docstrings, and line bounds. 

When an issue describes an `AttributeError` in a data transformation, the Localizer scans the skeleton hierarchy. It pinpoints the exact class and method in under 900 tokens of input, leaving all internal implementation lines stripped away.

### Stage 2: The Synthesizer (Surgical Edits Only)
Once the Localizer returns the suspect line numbers, the Synthesizer retrieves only those specific lines with a tight 15-line margin. 

We instruct the Synthesizer to follow Strunk's classic rule: omit needless code. The prompt forbids refactoring, reformatting, or renaming adjacent variables. It must produce a single, focused unified diff.

### Stage 3: The Verifier (Automated Sanity Gate)
Before any patch touches the repo, the Verifier runs an automated check using `git apply --check`. 

We enforce two hard invariants:
1. If the patch touches more than two files, it is rejected.
2. If the patch churn exceeds 80 lines, it is rejected.

In our experiments, whenever a 4-bit model produced more than 80 lines of changes for a single bug, it was almost always hallucinating. Rejecting these bloated patches prevented regressions.

---

## What the Data Showed: 60 Real Bug Fixes

We benchmarked this architecture against 60 real defect instances from popular open-source scientific Python repositories (including pandas, scikit-learn, and sympy). All runs executed offline on Kaggle L4x4 GPUs using `gemma-4-31b-it-qat-w4a16-ct`.

| What We Measured | Full-Context Baseline | AST Skeletonization | The Difference |
| :--- | :---: | :---: | :---: |
| **Mean Input Tokens** | 3,981 tokens | 877 tokens | **-77.97%** |
| **Defect Resolution Rate** | 48.33% (29/60) | 85.00% (51/60) | **+75.87% relative** |
| **Mean Latency per Issue** | 63.79 s | 15.53 s | **-75.65% faster** |
| **Patch Application Failures** | 23.33% (14/60) | 3.33% (2/60) | **-85.73% fewer breaks** |
| **12-Hour Issue Throughput** | 677 issues | 2,781 issues | **+310.78% capacity** |

By pruning context down to 877 mean tokens, resolution shot up from 48.3% to 85.0%. Just as importantly, average run time dropped from over a minute to 15.5 seconds. In a 12-hour evaluation window, that means our agent can process over 2,700 candidate issues instead of getting stuck on a few hundred.

---

## Where It Still Fails

The 15% of cases that our pipeline failed to resolve fell into two distinct categories:

1. **Dynamic Metaclass Tricks**: When libraries dynamically inject methods at runtime via `setattr` or custom metaclasses, static AST parsing cannot see the definition. The Localizer returns empty, and the agent falls back to broad textual search.
2. **Coupled Multi-Module Refactoring**: When an upstream interface change breaks four or five separate files at once, our two-file safety cap intentionally cuts the patch off. We chose safety over reckless edits, but this naturally limits multi-file fixes.

---

## Running the Code Yourself

All code, evaluation logs, and prompts are structured to run cleanly:

1. **Benchmark Evaluation**: Run `python paper/benchmark_harness.py` to replay the 60 defect tests offline.
2. **Read the Full Paper**: Open `paper/manuscript.pdf` for the complete mathematical derivation and proofs.
3. **Interactive Explorer**: Launch the [Live Web Simulator](https://zadevpenseo.github.io/gemma-4-developer-agent-ast/) in your browser or run `paper/visual_explainer.html` locally to test different context budgets and watch entropy curves shift in real time.
