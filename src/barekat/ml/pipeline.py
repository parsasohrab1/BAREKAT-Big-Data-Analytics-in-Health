"""ML pipeline orchestrator."""

from barekat.ml.clustering import PatientClusterer
from barekat.ml.readmission import ReadmissionPredictor


class MLPipeline:
    def __init__(self) -> None:
        self.readmission = ReadmissionPredictor()
        self.clustering = PatientClusterer()

    def run_all(self, data: dict) -> dict:
        results = {}
        results["readmission"] = self.readmission.train(data)
        results["clustering"] = self.clustering.train(data)
        results["alerts"] = len(self.readmission.generate_alerts(data))
        return results
