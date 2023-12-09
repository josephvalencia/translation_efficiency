# RNA-design

This repo implements `seqopt`, a lightweight library enabling users to perform model-based optimization using arbitrary nucleotide property models written in PyTorch. It can be installed via

```
pip install git+https://github.com/josephvalencia/RNA-design.git
```

`seqopt` was developed as part of a project titled "Extrapolative benchmarking of model-based discrete sampling methods for RNA design", presented at the 2023 Machine Learning in Computational Biology conference. Based on prior works, I developed models for predicting ribosome load of 5' UTRs, degradation properties of mRNAs, and toehold switch activities. Code for training these models and performing sequence optimization using the `seqopt` API is located in [MLCB](MLCB/). See the accepted [extended abstract](assets/MLCB_Discrete_Search_Nov.pdf) and [poster](assets/MLCB_Poster.pdf) for further details.

