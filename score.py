import os
import json
import argparse
from dataclasses import dataclass

THUNDERBIRD_MAPPING = {
  "a10b69e1-6034-4a2b-93e1-571d45194f75": "2ad9387a-65d8-4e33-ad5b-7580065a27ca", 
  "dd84e895-72fd-4023-a336-97689ded257c": "3d1682a7-0fb0-49ae-a4dc-a73afd2d06d5", 
  "9bc3cc16-074a-45ac-9bdc-b2a362e1daf3": "06fe7178-4491-4589-810f-2e2bc9502122", 
  "15c3b339-88f7-4a86-ab16-e71c58dcb01e": "7b6c7e24-c58a-49fc-a5bb-d57b80e5b4c3", 
  "f201fbc3-44e6-46fc-bcaa-432f9815454c": "030eeff7-b492-4218-b312-701ec99ee0cc", 
  "3f49d2cc-f400-4e7d-90cc-9b18e401cc31": "480bcfea-d68f-4aaa-a0a9-2589ef319381", 
  "3f28fe4f-5d9d-4994-a456-efd78cfae1a3": "6766f2b8-8a72-417f-a9e5-56fcaa735837", 
  "9b7bc335-06b5-4cd3-9119-1a649c478509": "35253b65-1c19-4304-8aa4-6884b8218fc0", 
  "a1af9f1c-50d5-4bc3-a51e-4d9b425ff638": "99146c54-4f37-4ab8-9327-5f3291665e1e", 
  "7b1e1ff9-bb85-49be-b01d-d6424be18cd0": "12086550-11c0-466b-b367-1d9e75b3910e", 
  "10a730d5-d414-4b40-b479-684bed1ae522": "94760984-3ff5-41ee-8347-cf1af709fea0", 
  "dfac9ee8-9bc4-4cdc-b465-4a4bfcd2f397": "bb5e4c0d-f964-439c-97b6-bdb9747de3f4", 
  "08c73485-7c6d-4681-999d-919f5c32dcfa": "c9e7eaf2-b1a1-4efc-a982-721972fa9f02", 
  "d38192b0-17dc-4e1d-99c3-786d0117de77": "d088f539-cab4-4f9a-ac92-9999fc3a656e", 
  "5203d847-2572-4150-912a-03f062254390": "e1e75309-3ddb-4d09-92ec-de869c928143"
} # from our keys to theirs


APPLICATIONS = set(["libreoffice_calc", "libreoffice_writer", "gimp", "libreoffice_impress", "vlc", "chrome", "vs_code", "thunderbird", "os", "multi_apps"]) 
HUMAN_PATH = "./"
EMPTY = "EMPTY"  # Used for UITARS

@dataclass(frozen=True)
class TaskMeta:
  application: str
  task_id: str

  def __str__(self):
    return f"{self.application}/{self.task_id}" if self.application is not EMPTY else f"{self.task_id[:100]}..."

@dataclass
class humanTask:
  single: list[str]
  grouped: list[list[str]]

@dataclass
class TaskTrajectory:
  num_steps: int
  task_result: float

@dataclass
class TaskScore:
  wes_plus: float
  wes_minus: float
  wes: float

def compute_task_score(task_meta: TaskMeta, human_task: humanTask, task_trajectory: TaskTrajectory, max_steps: int, single: bool) -> TaskScore:
  expected_steps = len(human_task.single) if single else len(human_task.grouped)

  if task_trajectory.num_steps < expected_steps and task_trajectory.task_result > 0.9 and not single:
    print(f"WARN: Task '{task_meta}' successfully completed in {task_trajectory.num_steps} instead of expected {expected_steps}")

  wes_plus = task_trajectory.task_result * expected_steps / task_trajectory.num_steps
  wes_minus =  - ((1 - task_trajectory.task_result) * task_trajectory.num_steps / max_steps)
  wes = wes_plus + wes_minus
  return TaskScore(wes_plus, wes_minus, wes)

def get_human_tasks(human_path: str, use_query: bool = False) -> dict[TaskMeta, humanTask]:
  """
  Load human tasks from the specified path.
  """

  human_tasks = {}
  num_task_files = 0
  num_task_files_opened = 0
  for application in os.listdir(human_path):
    if application not in APPLICATIONS:
      continue # skip for now
    app_path = os.path.join(os.path.join(human_path, application), "human")

    if os.path.isdir(app_path):
      for task_file in os.listdir(app_path):
        if task_file.endswith(".json"):
          num_task_files += 1
          with open(os.path.join(app_path, task_file), 'r') as f:
            num_task_files_opened += 1
            task_data = json.load(f)
            try:
              task_id = task_data["id"] if not use_query else task_data["instruction"] # for UITARS
              single = task_data["human-ground-truth"]["single-action"]
              grouped = task_data["human-ground-truth"]["grouped-action"]
            except Exception as e:
              print(f"Skipping task {task_file} due to exception: {e}")
              continue
            
            if use_query: # for UITARS
              human_tasks[TaskMeta(EMPTY, task_id)] = humanTask(single, grouped)
            else:
              human_tasks[TaskMeta(application, task_id)] = humanTask(single, grouped)
  return human_tasks

def get_task_trajectories(result_path: str) -> tuple[dict[TaskMeta, TaskTrajectory], int]:
  """
  Load task trajectories from the specified result path.
  """

  max_steps_empirical = 0

  task_trajectories = {}
  for application in os.listdir(result_path):
    if application not in APPLICATIONS:
      continue
    app_path = os.path.join(result_path, application)

    if os.path.isdir(app_path):
      for task_folder in os.listdir(app_path):
        full_task_folder_path = os.path.join(app_path, task_folder)
        if os.path.isdir(full_task_folder_path):
          for file in os.listdir(full_task_folder_path):
            if file.endswith(".jsonl"):
              file_path = os.path.join(full_task_folder_path, file)
              with open(file_path, 'r') as f:
                full_trajectory = []
                for line in f:
                  step_data = json.loads(line)
                  full_trajectory.append(step_data)
                task_id = task_folder
                num_steps = len(full_trajectory)
                max_steps_empirical = max(max_steps_empirical, num_steps)
              
              task_result_file_path = os.path.join(full_task_folder_path, 'result.txt')
              if not os.path.exists(task_result_file_path):
                print(f"Result file not found for {task_id} in {full_task_folder_path}")
                continue
              with open(task_result_file_path, 'r') as f:
                top_line = f.readlines()[0].strip()
                try:
                  task_result = float(top_line)
                except ValueError as e:
                  if top_line == "True":
                    task_result = 1.0
                  elif top_line == "False":
                    task_result = 0.0
                  else:
                    raise e
                task_trajectories[TaskMeta(application, task_id)] = TaskTrajectory(num_steps, task_result)
  return task_trajectories, max_steps_empirical

def get_task_trajectories_uitars(result_path: str) -> tuple[dict[TaskMeta, TaskTrajectory], int]:
  max_steps_empirical = 0

  task_trajectories = {}
  for task_folder in os.listdir(result_path):
    full_task_folder_path = os.path.join(result_path, task_folder)
    if os.path.isdir(full_task_folder_path):
      for file in os.listdir(full_task_folder_path):
        if file == "data.json":
          file_path = os.path.join(full_task_folder_path, file)
          with open(file_path, 'r') as f:
            task_data = json.load(f)
            num_steps = len(task_data)
            max_steps_empirical = max(max_steps_empirical, num_steps)
            task_result = task_data[-1]["inner_step"][0]["score"]
            
        elif file == "meta.json":
          file_path = os.path.join(full_task_folder_path, file)
          with open(file_path, 'r') as f:
            meta_data = json.load(f)
            query = meta_data["query"]
        
      task_trajectories[TaskMeta(EMPTY, query)] = TaskTrajectory(num_steps, task_result)
  return task_trajectories, max_steps_empirical


def get_and_display_aggregated_scores(task_scores: list[TaskScore], num_tasks: int):
  avg_wes_plus = sum(score.wes_plus for score in task_scores) / num_tasks
  avg_wes_minus = sum(score.wes_minus for score in task_scores) / num_tasks

  return avg_wes_plus, avg_wes_minus

def main(result_path, max_steps_scoring, is_uitars):
  human_tasks: dict[TaskMeta, humanTask] = get_human_tasks(HUMAN_PATH, is_uitars)
  num_human_tasks = len(human_tasks)
  print(f"Found {num_human_tasks} human tasks")

  print("Getting task trajectory")
  task_trajectories, max_steps_empirical = get_task_trajectories(result_path) if not is_uitars else get_task_trajectories_uitars(result_path)
  print(f"Found {len(task_trajectories)} trajectories.")

  max_steps = max(max_steps_scoring, max_steps_empirical)

  single_scores: list[TaskScore] = []
  grouped_scores: list[TaskScore] = []
  osworld_result = 0
  skipped_tasks = 0

  for task_meta, human_task in human_tasks.items():
    if task_meta not in task_trajectories:
      if task_meta.application == "thunderbird" and task_meta.task_id in THUNDERBIRD_MAPPING:
        task_meta = TaskMeta("thunderbird", THUNDERBIRD_MAPPING[task_meta.task_id])
        if task_meta not in task_trajectories:
          print(f"Task '{task_meta}' not found in trajectories, skipping with score of 0.")
          skipped_tasks += 1
          continue
      else:
        print(f"Task '{task_meta}' not found in trajectories, skipping with score of 0.")
        skipped_tasks += 1
        continue
    single_scores.append(compute_task_score(task_meta, human_task, task_trajectories[task_meta], max_steps, single=True))
    grouped_scores.append(compute_task_score(task_meta, human_task, task_trajectories[task_meta], max_steps, single=False))
    osworld_result += task_trajectories[task_meta].task_result

  print("\n=== RESULTS ===")
  print(f"Skipped {skipped_tasks} tasks that were not found in trajectories.")
  print(f"Original OSWorld Result: {osworld_result/num_human_tasks*100:.2f}% (on {num_human_tasks} human tasks)")

  single_action_wes_plus, wes_minus = get_and_display_aggregated_scores(single_scores, num_human_tasks)
  grouped_action_wes_plus, _ = get_and_display_aggregated_scores(grouped_scores, num_human_tasks)

  print(f"Single Action WES+: {single_action_wes_plus*100:.2f}")
  print(f"Grouped Action WES+: {grouped_action_wes_plus*100:.2f}")
  print(f"WES-: {wes_minus:.2f}")


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Score trajecories on OSWorld-Human")
  parser.add_argument("--result-path", type=str, help="Path to the full result directory.")
  parser.add_argument("--max-steps-scoring", type=int, default=15)
  parser.add_argument("--uitars", action='store_true', help="UI-TARS trajectories have a different structure.")
  args = parser.parse_args()

  main(args.result_path, args.max_steps_scoring, args.uitars)
