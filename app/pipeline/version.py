"""Pipeline version constant.

Change this value when pipeline stage order, stage input/output contracts,
segmentation logic, translation prompt strategy, formatting structure, or
export structure changes. Minor implementation changes must not change this.

Recorded in every JobRun at creation time for reproducibility.
"""
PIPELINE_VERSION = "0.5"
