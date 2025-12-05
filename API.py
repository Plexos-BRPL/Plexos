#Libraries
from operator import index
from eecloud.cloudsdk import CloudSDK
from eecloud.models import *
import pandas as pd
import tkinter as tk
import os
from tkinter import filedialog
import json
from pathlib import Path
import datetime
import shutil
from datetime import datetime
from typing import List
# Get the absolute path of the directory containing the current script
source_folder_path = Path(__file__).resolve().parent
OUTPUT_JSON_PATH = source_folder_path / "JSON Folder" # Path to save the output JSON file of simulations list
def Getfile_path_from_dialog():
       
    root = tk.Tk()# Create a Tkinter instance
    root.withdraw() 
        
   #opening file dialog for user to select the file path to get the model to run 
    file_path = filedialog.askopenfilename(
        title="Select Study List CSV File",
        filetypes=(("CSV files", "*.csv"), ("Excel files", "*.xlsx"), ("All files", "*.*"))
    )

    # 3. Destroy the Tkinter instance
    root.destroy()
    return file_path

file_path = Getfile_path_from_dialog()# Get the file path from the dialog

dotnet_exe_cli_path =r"C:\Program Files\plexos-cloud.exe"# Path to the Plexos Cloud SDK CLI executable

pxc = CloudSDK(dotnet_exe_cli_path)# Initialize the CloudSDK with the path to the CLI executable

command_responses = pxc.auth.login_client_credentials(use_client_credentials=True, client_id="61c1194d-3f1b-48e9-b569-9cbf9ea37592", client_secret="TZGlZaclKvs4P6vaXNwN+Juu3Lo2uggV/xGR6aLILrI=",tenant_id="daf6c8ef-a23e-4f1d-a9de-dd597e307c73", print_message=True)# Log in using Sovendra Jha Sir Cloud credentials
try:
     #Loggin in using Crediatials 
     last_command_response: CommandResponse[Contracts_LoginResponse] = pxc.auth.get_final_response(command_responses)
     
     if last_command_response is not None and last_command_response.Status == "Success":         
         data: Contracts_LoginResponse = last_command_response.EventData
         print(f"Login successful: {data.IsLoggedIn}")
     else:
         print("Login failed or no response received.")

except Exception as e:
     print(f"An error occurred during login: {e}")

def GetStudyID(study_name: str) -> str:
    # Function to get Study ID by Study Name
    command_responses = pxc.study.find_study(
        study_name=study_name, 
        print_message=True
    )
    last_command_response: CommandResponse[Contracts_ListStudiesResponse] = pxc.solution.get_final_response(command_responses)# Get the final response from the command responses
    if last_command_response is not None and last_command_response.Status == "Success":# Check if the response is successful
        data: Contracts_ListStudiesResponse = last_command_response.EventData
        
        for study in data.Studies:
            return study.Id.Value# Return the Study ID Value
    return None

def GetSimulationList(study_id: str, model_name: str,Study_name: str) -> pd.DataFrame:
    """
    Fetches the list of simulations for a given study ID, filters them by model name, 
    prints the IDs and status of the filtered simulations, and saves the full list 
    of records to a JSON file.
    """
    print(f"Fetching simulations for Study ID: {study_id} and Model Name: {model_name}")
    date=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # 1. Execute the list_simulations command
    # Use order_by and descending for consistency with the example logic
    simulations_response: list[CommandResponse[Contracts_ListSimulationResponse]] = pxc.simulation.list_simulations(
        study_id=study_id, order_by="LastUpdatedAt", descending=True, top=1,print_message=True
    )
    
    last_command_response: CommandResponse[Contracts_ListSimulationResponse] = pxc.simulation.get_final_response(simulations_response)
    
    if last_command_response is not None and last_command_response.Status == "Success":
        data: Contracts_ListSimulationResponse = last_command_response.EventData
        
        # Check if the list of simulations exists and is not None.
        simulation_list = getattr(data, 'Simulations', None) or getattr(data, 'SimulationRecords', None)
        
        if simulation_list:
            
            # --- START of New Logic: Filter and Print ---
            
            # Step 5: Filter simulations by model name (Case-sensitive matching)
            filtered_simulations = [
                sim for sim in simulation_list 
                if hasattr(sim, 'ModelIdentifiers') and any(
                    model.Name == model_name for model in sim.ModelIdentifiers
                )
            ]

            if not filtered_simulations:
                print(f"No simulations found for study ID: {study_id} and model name: {model_name}.")
            else:
                print(f"\nSimulations found ({len(filtered_simulations)} total):")
                for sim in filtered_simulations:
                    # Safely access attributes like Id.Value
                    sim_id = sim.Id.Value if hasattr(sim.Id, 'Value') else 'N/A'
                    sim_status = sim.Status if hasattr(sim, 'Status') else 'N/A'
                    sim_created = sim.CreatedAt if hasattr(sim, 'CreatedAt') else 'N/A'
                    print(f"  Simulation ID: {sim_id}, Status: {sim_status}, Created At: {sim_created}")
            
        
            
            # 2. Convert the full list of simulation objects to a Pandas DataFrame
            records = [record.to_dict() for record in simulation_list if hasattr(record, 'to_dict')]
            df = pd.DataFrame(records)
            
            # 3. Save the full DataFrame to JSON
            try:
                df.to_json(OUTPUT_JSON_PATH/f"{date}_simulation_list_{Study_name}_{model_name}.json", orient='records', indent=4)
                print(f" Full simulation list successfully saved to {OUTPUT_JSON_PATH}")
                return df
                
            except Exception as e:
                print(f" An error occurred while saving the JSON file: {e}")
        else:
            print("No simulation records found in the response data.")
            
    else:
        status = last_command_response.Status if last_command_response else "No response received"
        print(f"Failed to retrieve simulation list. Status: {status}")
        
    return None
  
def ProcessStudiesAndGetSimulations(file_path: str, OUTPUT_JSON_PATH: str):
    """
    Reads the input file (CSV/Excel), finds Study IDs, calls 
    GetSimulationList_AndFilter for each study/model pair, and saves 
    all collected, filtered simulation data to a single JSON file.
    """
    
    # 0. File Type Check and Reading
    file_extension = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_extension in ['.xlsx', '.xls']:
            print(f"Reading file as Excel: {file_path}")
            df = pd.read_excel(file_path)
        elif file_extension == '.csv':
            print(f"Reading file as CSV: {file_path}")
            df = pd.read_csv(file_path)
        else:
            print(f"Error: Unsupported file format '{file_extension}'. Please use .csv, .xlsx, or .xls.")
            return 
            
    except FileNotFoundError:
        print(f"Error: The file was not found at {file_path}")
        return
    except Exception as e:
        print(f"An error occurred while reading the file: {e}")
        return

    # 1. Case-Insensitive Column Lookup for 'Name' and 'Model Name'
    name_column = None
    model_name_column = None
    
    for col in df.columns:
        col_lower = col.lower()
        if col_lower == 'name':
            name_column = col
        elif col_lower == 'model name' or col_lower == 'modelname':
            model_name_column = col
            
    if name_column is None:
        print("Error: Could not find a column named 'Name' (case-insensitive) in the data.")
        return 
    if model_name_column is None:
        print("Error: Could not find a column named 'Model Name' (case-insensitive) in the data.")
        return
        
    # Prepare the data for iteration as a list of (StudyName, ModelName) tuples
    # Use .itertuples for efficient row iteration
    study_model_list = df[[name_column, model_name_column]].itertuples(index=False, name=None)
    
    # 2. Iterate, Get Study ID, and Call Simulation Function for EACH Study
    
    
    try: 
        for name_input, model_name_input in study_model_list:
            
            # Data Cleaning and Validation
            if pd.isna(name_input) or pd.isna(model_name_input):
                print("\nSkipping row with missing Study Name or Model Name.")
                continue
                
            name_str = str(name_input).strip()
            model_name_str = str(model_name_input).strip()
            
            # Get Study ID (Requires the GetStudyID function to be defined/available)
            study_id = GetStudyID(name_str) 
            
            if not study_id:
                print(f"\nStudy '{name_str}' not found or failed to retrieve ID. Skipping simulation lookup.")
                continue 
            
            print(f"\n--- Processing Study '{name_str}' (ID: {study_id}) ---")
            
            # --- Call the Simulation Retrieval Function ---
         
            GetSimulationList(study_id,model_name_str,name_str)
            
    except Exception as e:
        print(f"An error occurred during overall processing: {e}")
        return None
        
    # 3. Final Save of ALL Collected Simulation Data (outside the loop)
    
    return None

    ProcessStudiesAndGetSimulations(file_path, OUTPUT_JSON_PATH)
ProcessStudiesAndGetSimulations(file_path,OUTPUT_JSON_PATH)



#work till 50 12 25  now interagte the simulation json to enqueue and delete the original json file 








def process_and_enqueue_simulations(source_folder: str, backup_base_folder: str):
    """
    1. Creates a dated backup folder outside the source folder.
    2. Copies all JSON files from the source folder to the backup folder.
    3. Iterates through the original JSON files.
    4. Enqueues the simulation using the API.
    5. Deletes the original JSON file upon successful enqueuing.
    """
    
    # 1. Prepare Dated Backup Folder
    today_date = datetime.now().strftime("%Y%m%d")
    backup_folder_name = f"JSON_Backup_{today_date}"
    backup_path = os.path.join(backup_base_folder, backup_folder_name)
    
    try:
        os.makedirs(backup_path, exist_ok=True)
        print(f"✅ Created/Ensured backup folder: {backup_path}")
    except Exception as e:
        print(f"❌ Error creating backup folder: {e}")
        return

    # 2. Get all JSON files
    json_files: List[str] = [f for f in os.listdir(source_folder) if f.endswith('.json')]
    
    if not json_files:
        print(f"⚠️ No JSON files found in {source_folder}. Exiting.")
        return

    # 3. Copy files to backup and prepare for iteration
    original_file_paths = []
    
    print("\n--- Copying Files to Backup ---")
    for filename in json_files:
        original_path = os.path.join(source_folder, filename)
        backup_path_full = os.path.join(backup_path, filename)
        
        try:
            shutil.copy2(original_path, backup_path_full) # copy2 preserves metadata
            original_file_paths.append(original_path)
        except Exception as e:
            print(f"❌ Failed to copy {filename}: {e}")
            
    print(f"✅ Successfully copied {len(original_file_paths)} files to backup.")
    
    # 4. Iterate, Enqueue, and Delete
    print("\n--- Enqueuing and Deleting Files ---")
    
    for file_path in original_file_paths:
        filename = os.path.basename(file_path)
        print(f"\nProcessing: {filename}")
        
        try:
            # 4a. API Call to Enqueue Simulation
            command_responses = pxc.simulation.enqueue_simulation(file_path=file_path, print_message=True)
            last_command_response: CommandResponse = pxc.simulation.get_final_response(command_responses)
            
            # 4b. Check API Status
            if last_command_response is not None and last_command_response.Status == "Success":
                data: Contracts_EnqueueSimulationResponse = last_command_response.EventData
                print(f"  ✅ Enqueue Success. Details: {data}")
                
                # 4c. Delete the original file
                os.remove(file_path)
                print(f"  🗑️ Deleted original file: {filename}")
                
            else:
                status = last_command_response.Status if last_command_response else "Unknown"
                print(f"  ⚠️ Enqueue Failed (Status: {status}). File NOT deleted.")
                
        except Exception as e:
            print(f"  ❌ An error occurred during API or deletion for {filename}: {e}")

BACKUP_BASE_FOLDER = os.path.dirname(OUTPUT_JSON_PATH)

process_and_enqueue_simulations(OUTPUT_JSON_PATH, BACKUP_BASE_FOLDER)


def GetStudyList() -> list:
    command_responses = pxc.study.list_studies(print_message=True)# List all studies
    last_command_response: CommandResponse[Contracts_ListStudiesResponse] = pxc.solution.get_final_response(command_responses)# Get the final response from the command responses
    studies_list = []
    if last_command_response is not None and last_command_response.Status == "Success":# Check if the response is successful
        data: Contracts_ListStudiesResponse = last_command_response.EventData# Get the event data from the response
        studies_list = data.Studies
        records = []# Create an empty list to store records
        for study in studies_list:
            record = {
            'Id': study.Id.Value if hasattr(study.Id, 'Value') else study.Id,
            'Name': study.Name,
            }
            records.append(record)
        df = pd.DataFrame(records)
        df.to_csv(r"C:\Users\plexos\Desktop\Study_list.csv", index=False)
        print(f"Successfully saved {len(df)} studies to Desktop as 'Study_list.csv'.")
    return "List Generated Successfully"

