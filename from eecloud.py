from eecloud.cloudsdk import CloudSDK, SDKBase
from eecloud.models import *

CLI_PATH: str = "cloud_cli_path"  # Path to the Cloud CLI
ENVIRONMENT: str = "<cloud_env>"  # Target environment (e.g., "Aquila", "PreProd")
SDK_DEBUG_MESSAGES: bool = False

def main() -> None:
    # Initialization
    pxc: CloudSDK = CloudSDK(cli_path=CLI_PATH)

    # Step 1: Set environment
    env_response: list[CommandResponse[Contracts_EnvironmentResponse]] = pxc.environment.set_user_environment(
        environment=ENVIRONMENT, print_message=SDK_DEBUG_MESSAGES
    )
    env_final: Contracts_EnvironmentResponse = SDKBase.get_response_data(env_response)

    # Step 2: Authenticate user
    auth_response: list[CommandResponse[Contracts_LoginResponse]] = pxc.auth.login(print_message=SDK_DEBUG_MESSAGES)
    auth_final: Contracts_LoginResponse = SDKBase.get_response_data(auth_response)

    if not auth_final or not auth_final.IsLoggedIn:
        raise RuntimeError("Authentication failed. Please check your credentials.")

    # Step 3: Define study ID and model name
    study_id: str = "<your_study_id>"  # Replace with your study ID
    model_name: str = "<your_model_name>"  # Replace with your model name

    # Step 4: Retrieve simulations filtered by study ID and model name
    simulations_response: list[CommandResponse[Contracts_ListSimulationResponse]] = pxc.simulation.list_simulations(
        study_id=study_id, order_by=["CreatedAt"], descending=True, print_message=SDK_DEBUG_MESSAGES
    )
    simulations_final: Contracts_ListSimulationResponse = SDKBase.get_response_data(simulations_response)

    if not simulations_final or not simulations_final.SimulationRecords:
        print(f"No simulations found for study ID: {study_id}")
        return

    # Step 5: Filter simulations by model name
    filtered_simulations = [
        sim for sim in simulations_final.SimulationRecords if any(model.Name == model_name for model in sim.ModelIdentifiers)
    ]

    if not filtered_simulations:
        print(f"No simulations found for study ID: {study_id} and model name: {model_name}")
    else:
        print(f"Simulations for study ID: {study_id} and model name: {model_name}:")
        for sim in filtered_simulations:
            print(f"Simulation ID: {sim.Id.Value}, Status: {sim.Status}, Created At: {sim.CreatedAt}")

if __name__ == "__main__":
    main()





def ProcessStudiesAndGetSimulations(file_path: str, OUTPUT_JSON_PATH: str):
    
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
        print("Error: Could not find a column named 'Model Name' in the data.")
        return
        
    # Combine the columns into a list of tuples for easy iteration
    study_list = df[[name_column, model_name_column]].itertuples(index=False, name=None)
    
    # 2. Iterate, Get Study ID, and Process Simulations for EACH Study
    all_study_simulations = [] 
    
    try: 
        # Iterate over the rows, getting the name and model_name for each record
        for name_input, model_name_input in study_list:
            
            # Data Cleaning and Validation
            if pd.isna(name_input) or pd.isna(model_name_input):
                print("Skipping row with missing Study Name or Model Name.")
                continue
                
            name_str = str(name_input).strip()
            model_name_str = str(model_name_input).strip()
            
            # 2a. Get Study ID
            study_id = GetStudyID(name_str)
            
            if not study_id:
                print(f"Study '{name_str}' not found or failed to retrieve ID. Skipping simulation lookup.")
                continue 
            
            print(f"\n--- Processing Study '{name_str}' (ID: {study_id}) with Model '{model_name_str}' ---")
            
            # 2b. Execute the list_simulations command
            simulations_response: list[CommandResponse[Contracts_ListSimulationResponse]] = pxc.simulation.list_simulations(
                study_id=study_id, order_by="LastUpdatedAt", descending=True, top=1, print_message=True
            )
            
            last_command_response: CommandResponse[Contracts_ListSimulationResponse] = pxc.simulation.get_final_response(simulations_response)
            
            if last_command_response is not None and last_command_response.Status == "Success":
                data: Contracts_ListSimulationResponse = last_command_response.EventData
                simulation_list = getattr(data, 'Simulations', None) or getattr(data, 'SimulationRecords', None)
                
                if simulation_list:
                    
                    # 2c. Filter simulations by the specific model name from the Excel row
                    filtered_simulations = [
                        sim for sim in simulation_list 
                        if hasattr(sim, 'ModelIdentifiers') and any(
                            # Use the model_name_str read from the file for filtering
                            model.Name == model_name_str for model in sim.ModelIdentifiers
                        )
                    ]

                    if not filtered_simulations:
                        print(f"No simulations found matching model: '{model_name_str}' in this study.")
                    else:
                        print(f"Simulations found ({len(filtered_simulations)} total):")
                        
                        # 2d. Print filtered results and collect full records
                        for sim in filtered_simulations:
                            sim_id = sim.Id.Value if hasattr(sim.Id, 'Value') else 'N/A'
                            sim_status = sim.Status if hasattr(sim, 'Status') else 'N/A'
                            sim_created = sim.CreatedAt if hasattr(sim, 'CreatedAt') else 'N/A'
                            print(f"  ➡️ Simulation ID: {sim_id}, Status: {sim_status}, Created At: {sim_created}")
                            
                            # Add study context to the collected data
                            record = sim.to_dict() if hasattr(sim, 'to_dict') else {}
                            record['StudyName'] = name_str
                            record['StudyID'] = study_id
                            record['InputModelName'] = model_name_str # Record the model name used for filtering
                            all_study_simulations.append(record)
                            
                else:
                    print(f"No simulation records found for Study '{name_str}'.")
            else:
                status = last_command_response.Status if last_command_response else "No response received"
                print(f"Failed to retrieve simulations for Study '{name_str}'. Status: {status}")
                
    except Exception as e:
        print(f"An error occurred during study/simulation lookup: {e}")
        return None
        
    # 3. Final Save of ALL Collected Simulation Data (outside the loop)
    if all_study_simulations:
        df_all = pd.DataFrame(all_study_simulations)
        
        # Use a generic name for the output file since model name is now dynamic
        output_file_name = f"simulations_processed_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = os.path.join(OUTPUT_JSON_PATH, output_file_name) 

        try:
            df_all.to_json(output_path, orient='records', indent=4)
            print(f"\n✅ All filtered simulation records from all studies saved to {output_path}")
            return df_all
        except Exception as e:
            print(f"\n❌ An error occurred while saving the final JSON file: {e}")
            
    else:
        print("\nNo simulations were found across all studies that matched the criteria.")
        
    return None