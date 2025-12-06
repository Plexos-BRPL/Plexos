from eecloud.cloudsdk import CloudSDK
from eecloud.models import *
import pandas as pd
import tkinter as tk
from tkinter import filedialog
import os
from pathlib import Path
import shutil
from datetime import datetime
from typing import List, Dict, Optional
import time

class SimulationWorkflowManager:
    """
    Manages the end-to-end workflow for finding the latest simulation, 
    downloading its request file, enqueuing it, monitoring its progress, 
    and downloading the final solution using the PLEXOS Cloud SDK.
    """
    
    # --- Configuration and Initialization ---

    # Define the polling interval in seconds (30 minutes)
    # Rationale: This value is chosen to avoid overloading the API while waiting for long simulations.
    POLLING_INTERVAL_SECONDS = 30 * 60 
    
    # Define potential solution types for download
    # Rationale: These types specify the exact data package (Hybrid, Results, Metadata) 
    # we want to retrieve upon simulation completion.
    SOLUTION_TYPES = ["Hybrid", "Results", "Metadata"] 
    
    def __init__(self, dotnet_exe_path: str, client_id: str, client_secret: str, tenant_id: str, base_dir: Path):
        """
        Initializes the workflow manager with necessary paths and credentials.
        """
        self.pxc = CloudSDK(dotnet_exe_path)
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        
        # Define output paths relative to the base directory
        self.DOWNLOAD_OUTPUT_FOLDER = base_dir / "Downloaded_Simulations"
        self.SOLUTION_OUTPUT_FOLDER = base_dir / "Solutions_Output"
        self.BACKUP_BASE_FOLDER = base_dir.parent # Set backup one level up for safety

        # Ensure required folders exist, as the script needs guaranteed paths to write files.
        self.DOWNLOAD_OUTPUT_FOLDER.mkdir(exist_ok=True, parents=True)
        self.SOLUTION_OUTPUT_FOLDER.mkdir(exist_ok=True, parents=True)
        print(f"Workflow manager initialized.")
        print(f"Download folder: {self.DOWNLOAD_OUTPUT_FOLDER}")
        print(f"Solution folder: {self.SOLUTION_OUTPUT_FOLDER}")
        
    def _login(self) -> bool:
        """
        Logs into the Cloud SDK using client credentials.
        """
        command_responses = self.pxc.auth.login_client_credentials(
            use_client_credentials=True,
            client_id=self.client_id,
            client_secret=self.client_secret,
            tenant_id=self.tenant_id,
            print_message=True
        )
        try:
            last_command_response: CommandResponse[Contracts_LoginResponse] = self.pxc.auth.get_final_response(command_responses)
            if last_command_response and last_command_response.Status == "Success":
                print(f"Login successful: {last_command_response.EventData.IsLoggedIn}")
                return True
            else:
                print("Login failed or no response received.")
                return False
        except Exception as e:
            print(f"An error occurred during login: {e}")
            return False

    def _get_study_id(self, study_name: str) -> str:
        """
        Retrieves the Study ID corresponding to a given Study Name.
        Rationale: The API requires a unique Study ID (GUID) for most subsequent calls 
        like listing simulations.
        """
        command_responses = self.pxc.study.find_study(
            study_name=study_name,
            print_message=False
        )
        last_command_response: CommandResponse[Contracts_ListStudiesResponse] = self.pxc.study.get_final_response(command_responses)
        if last_command_response and last_command_response.Status == "Success" and last_command_response.EventData.Studies:
            return last_command_response.EventData.Studies[0].Id.Value
        return None

    def _get_latest_simulation_id(self, study_id: str, model_name: str) -> str:
        """
        Retrieves the ID of the latest completed simulation for a specific model within a study.
        Rationale: The user wants the input file for the *most recent* run of the specified model.
        """
        simulations_response: list[CommandResponse[Contracts_ListSimulationResponse]] = self.pxc.simulation.list_simulations(
            study_id=study_id, order_by="CreatedAt", descending=True, top=100, print_message=False
        )
        last_command_response: CommandResponse[Contracts_ListSimulationResponse] = self.pxc.simulation.get_final_response(simulations_response)

        if last_command_response and last_command_response.Status == "Success":
            simulation_list = getattr(last_command_response.EventData, 'Simulations', None) or getattr(last_command_response.EventData, 'SimulationRecords', None)
            if simulation_list:
                # Filter by model name because a study can contain multiple models.
                filtered_simulations = [
                    sim for sim in simulation_list
                    if hasattr(sim, 'ModelIdentifiers') and any(
                        model.Name == model_name for model in sim.ModelIdentifiers
                    )
                ]
                if filtered_simulations:
                    # Sort again to guarantee the absolute latest after filtering.
                    latest_sim = sorted(
                        filtered_simulations,
                        key=lambda x: datetime.strptime(x.CreatedAt, '%Y-%m-%dT%H:%M:%S.%fZ') if hasattr(x, 'CreatedAt') else datetime.min,
                        reverse=True
                    )[0]
                    sim_id = latest_sim.Id.Value if hasattr(latest_sim.Id, 'Value') else None
                    if sim_id:
                        print(f"  Found latest Simulation ID: **{sim_id}** (Created At: {latest_sim.CreatedAt})")
                        return sim_id
        return None

    def _download_simulation_file(self, simulation_id: str, study_id: str, model_name: str) -> Path | None:
        """
        Downloads the simulation request (.txt) file associated with a historical simulation ID.
        Rationale: The downloaded request file is the input needed to create a *new* simulation run (enqueue).
        """
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{study_id}_{model_name}_{date_str}.txt"
        print(f"  Attempting to download Simulation ID: {simulation_id} as '{file_name}'...")

        command_responses = self.pxc.simulation.build_simulation_request_from_id(
            simulation_id=simulation_id,
            output_directory=str(self.DOWNLOAD_OUTPUT_FOLDER),
            file_name=file_name,
            overwrite=True,
            study_id=study_id,
            model_name=model_name,
            print_message=False
        )
        last_command_response: CommandResponse[Contracts_BuildSimulationRequestFromIdResponse] = self.pxc.simulation.get_final_response(command_responses)

        if last_command_response and last_command_response.Status == "Success":
            output_path = self.DOWNLOAD_OUTPUT_FOLDER / file_name
            print(f"  Download Success. File saved to: **{output_path}**")
            return output_path
        else:
            print(f"  Download Failed. Status: {last_command_response.Status if last_command_response else 'Unknown'}")
            return None

    def _enqueue_simulations(self) -> List[str]:
        """
        Enqueues all downloaded .txt files and returns a list of new Simulation IDs.
        """
        print("\n" + "="*50)
        print("Starting Enqueue and Backup Process")
        print("="*50)

        # 1. Prepare Dated Backup Folder
        today_date = datetime.now().strftime("%Y%m%d")
        backup_folder_name = f"Simulation_Backup_{today_date}"
        backup_path = self.BACKUP_BASE_FOLDER / backup_folder_name
        backup_path.mkdir(parents=True, exist_ok=True)

        # 2. Get all .txt files
        sim_files: List[Path] = list(self.DOWNLOAD_OUTPUT_FOLDER.glob('*.txt'))
        successful_enqueue_ids = []

        if not sim_files:
            print("No simulation files (.txt) found for enqueue. Skipping.")
            return []

        # 3. Copy files to backup (prevents data loss)
        original_file_paths = []
        for file_path in sim_files:
            backup_path_full = backup_path / file_path.name
            shutil.copy2(file_path, backup_path_full)
            original_file_paths.append(file_path)

        # 4. Iterate, Enqueue, and Delete
        print("\n--- Enqueuing and Deleting Files ---")
        for file_path in original_file_paths:
            try:
                # The API call uses the downloaded .txt file to create a new simulation run.
                command_responses = self.pxc.simulation.enqueue_simulation(file_path=str(file_path), print_message=False)
                last_command_response: CommandResponse = self.pxc.simulation.get_final_response(command_responses)

                if last_command_response and last_command_response.Status == "Success":
                    sim_id = last_command_response.EventData.Id.Value
                    print(f"  Enqueue Success. New Simulation ID: **{sim_id}**")
                    # Track the ID of the *new* simulation to monitor it later.
                    successful_enqueue_ids.append(sim_id) 

                    # Delete the original .txt file to prevent re-enqueuing.
                    file_path.unlink()
                    print(f"  Deleted original file: {file_path.name}")
                else:
                    print(f"  Enqueue Failed (Status: {last_command_response.Status if last_command_response else 'Unknown'}). File NOT deleted.")
            except Exception as e:
                print(f"  An error occurred during API or deletion for {file_path.name}: {e}")
                
        return successful_enqueue_ids

    def _download_solution(self, solution_id: str, study_id: str, sim_id: str, solution_type: str) -> bool:
        """Downloads a specific solution type for a given simulation."""
        
        # A unique sub-directory is created for each simulation to keep files organized.
        sim_output_dir = self.SOLUTION_OUTPUT_FOLDER / f"{study_id}_{sim_id}"
        sim_output_dir.mkdir(exist_ok=True, parents=True)
        
        print(f"    Downloading **{solution_type}** solution for SIM ID: {sim_id}...")

        command_responses = self.pxc.solution.download_solution(
            solution_id=solution_id,
            output_directory=str(sim_output_dir),
            solution_type=solution_type,
            overwrite=True,
            create_directory=True,
            print_message=False
        )
        
        last_command_response: CommandResponse[Contracts_DownloadSolution] = self.pxc.solution.get_final_response(command_responses) 
        
        if last_command_response and last_command_response.Status == "Success":
            print(f"    Download Success: {solution_type} saved to {sim_output_dir}")
            return True
        else:
            print(f"    Download Failed for {solution_type}. Status: {last_command_response.Status if last_command_response else 'Unknown'}")
            return False

    def _monitor_and_download(self, input_file_path: str, sim_ids_to_monitor: List[str]):
        """
        Continuously checks simulation progress and downloads solutions when complete.
        """
        print("\n" + "="*50)
        print(f"Starting Simulation Monitor (Polling every {self.POLLING_INTERVAL_SECONDS/60} minutes)")
        print("="*50)
        
        # 1. Read the input file to map new Sim IDs back to Study IDs.
        df = pd.read_excel(input_file_path) if input_file_path.endswith(('.xlsx', '.xls')) else pd.read_csv(input_file_path)
            
        monitoring_map: Dict[str, Dict[str, str]] = {}
        for index, row in df.iterrows():
            sim_id = str(row['Simulation ID'])
            study_id = str(row['Study ID'])
            if sim_id in sim_ids_to_monitor:
                monitoring_map[sim_id] = {'Study ID': study_id}
        
        if not monitoring_map:
            print("No successfully enqueued Simulation IDs to monitor. Exiting monitor.")
            return

        simulations_status = {sim_id: "QUEUED" for sim_id in monitoring_map}
        
        # 2. Main Monitoring Loop
        while any(status in ["QUEUED", "RUNNING"] for status in simulations_status.values()):
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n--- POLLING CYCLE STARTED: {timestamp} ---")
            
            for sim_id, status in simulations_status.items():
                if status in ["COMPLETED", "FAILED", "Canceled"]:
                    continue
                
                print(f"  Checking progress for SIM ID: {sim_id}...")
                command_responses = self.pxc.simulation.check_simulation_progress(
                    simulation_id=sim_id, 
                    print_message=False
                )
                last_command_response: CommandResponse[Contracts_CheckSimulationProgressResponse] = self.pxc.simulation.get_final_response(command_responses)
                
                if last_command_response and last_command_response.Status == "Success":
                    data: Contracts_CheckSimulationProgressResponse = last_command_response.EventData
                    current_status = data.Status
                    
                    print(f"    Current Status: **{current_status}** (Progress: {data.PercentComplete}%)")
                    
                    if current_status == "Completed":
                        print(f"  SIMULATION **{sim_id}** HAS COMPLETED! Starting solution download.")
                        simulations_status[sim_id] = "COMPLETED"
                        
                        solution_id = data.SolutionId.Value if hasattr(data.SolutionId, 'Value') else None
                        study_id = monitoring_map[sim_id]['Study ID']
                        
                        if solution_id:
                            for s_type in self.SOLUTION_TYPES:
                                self._download_solution(solution_id, study_id, sim_id, s_type)
                        else:
                            print("  Solution ID not available for download.")
                            
                    elif current_status in ["Failed", "Canceled"]:
                        print(f"  SIMULATION **{sim_id}** status: **{current_status}**. Skipping download.")
                        simulations_status[sim_id] = current_status
                    else:
                        simulations_status[sim_id] = current_status
                else:
                    simulations_status[sim_id] = "FAILED"
                    print("  Failed to retrieve progress status for this simulation.")
                    
            if all(status in ["COMPLETED", "FAILED", "Canceled"] for status in simulations_status.values()):
                print("\nAll simulations have finished processing. Exiting monitor.")
                break
                
            print(f"\nSleeping for {self.POLLING_INTERVAL_SECONDS/60} minutes...")
            time.sleep(self.POLLING_INTERVAL_SECONDS)

    # --- Public Execution Method ---

    def execute_workflow(self):
        """
        Orchestrates the entire simulation workflow from login to solution download.
        """
        if not self._login():
            print("Workflow halted due to login failure.")
            return

        # 1. Get the input file path from the user
        root = tk.Tk()
        root.withdraw()
        input_file_path = filedialog.askopenfilename(
            title="Select Study List CSV/Excel File",
            filetypes=(("Data files", "*.csv *.xlsx *.xls"), ("All files", "*.*"))
        )
        root.destroy()

        if not input_file_path:
            print("No input file selected. Exiting.")
            return

        # Read the file and detect file type
        file_path = Path(input_file_path)
        file_extension = file_path.suffix.lower()

        try:
            if file_extension in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
                write_func = lambda df, path: df.to_excel(path, index=False)
            elif file_extension == '.csv':
                df = pd.read_csv(file_path)
                write_func = lambda df, path: df.to_csv(path, index=False)
            else:
                print(f"Error: Unsupported file format '{file_extension}'.")
                return
        except Exception as e:
            print(f"An error occurred while reading the file: {e}")
            return

        # Ensure required columns are present/initialized
        name_column = next((col for col in df.columns if col.lower() == 'name'), None)
        model_name_column = next((col for col in df.columns if col.lower() in ['model name', 'modelname']), None)
        sim_id_column = 'Simulation ID'
        study_id_col = 'Study ID'
        
        if not name_column or not model_name_column:
            print("Error: Could not find required columns ('Name' and 'Model Name').")
            return

        if sim_id_column not in df.columns:
            df[sim_id_column] = None
        if study_id_col not in df.columns:
            df[study_id_col] = None
        
        # 2. Process each study/model pair
        for index, row in df.iterrows():
            name_str = str(row[name_column]).strip()
            model_name_str = str(row[model_name_column]).strip()

            if not name_str or not model_name_str or name_str == 'nan' or model_name_str == 'nan':
                print(f"\nSkipping row {index + 1} due to missing data.")
                continue
                
            print(f"\n--- Processing Row {index + 1} ---")
            print(f"Study: **{name_str}**, Model: **{model_name_str}**")

            study_id = self._get_study_id(name_str)
            df.loc[index, study_id_col] = study_id

            if not study_id:
                print(f"  Study '{name_str}' not found. Skipping download.")
                continue

            latest_sim_id = self._get_latest_simulation_id(study_id, model_name_str)

            if latest_sim_id:
                df.loc[index, sim_id_column] = latest_sim_id
                # Download the file to prepare for enqueuing later.
                self._download_simulation_file(latest_sim_id, study_id, model_name_str)
            else:
                df.loc[index, sim_id_column] = "NOT_FOUND"
                print(f"  No latest simulation ID found for '{name_str}' and '{model_name_str}'.")

        # 3. Save the updated DataFrame back to the original file
        print("\n" + "="*50)
        print("Saving Updated Input File...")
        try:
            write_func(df, file_path)
            print(f"Input file successfully updated with IDs: **{file_path}**")
        except Exception as e:
            print(f"An error occurred while saving the updated file: {e}")
            
        # 4. Enqueue the downloaded files
        successful_enqueue_ids = self._enqueue_simulations()

        # 5. Monitor progress and download solutions
        if successful_enqueue_ids:
            self._monitor_and_download(str(file_path), successful_enqueue_ids)
        else:
            print("\nNo simulations were successfully enqueued. Monitoring skipped.")
        
        print("\nWorkflow execution finished.")


# --- Main Execution Block ---

if __name__ == "__main__":
    
    # Configuration Details (Replace with actual values)
    DOTNET_EXE_PATH = r"C:\Program Files\plexos-cloud.exe"
    CLIENT_ID = "61c1194d-3f1b-48e9-b569-9cbf9ea37592"
    CLIENT_SECRET = "TZGlZaclKvs4P6vaXNwN+Juu3Lo2uggV/xGR6aLILrI="
    TENANT_ID = "daf6c8ef-a23e-4f1d-a9de-dd597e307c73"
    
    # Use the script's current directory as the base for all output folders
    BASE_OUTPUT_DIR = Path(__file__).resolve().parent

    # Initialize and execute the workflow manager
    manager = SimulationWorkflowManager(
        dotnet_exe_path=DOTNET_EXE_PATH,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        tenant_id=TENANT_ID,
        base_dir=BASE_OUTPUT_DIR
    )
    
    manager.execute_workflow()