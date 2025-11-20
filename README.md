# Plexos
This Repo contains all the necessary files of BRPL Plexos Model and this Read Me tell about what was the thinking process about behind whole model.

Model Structure Overview.
1. Generators:
In Generator Class for each Region (ie: NR, SR, WR, ER and NER) there will be separate generator which then further connected to respective Generation Node (NR Generation, SR Generation, WR Generation, ER Generation and NER Generation).
2. Regions:
For Region only one Northern Region (NR) is declared as our network reside in Northern Region only.
In this region we have relation with majorly 2 class:
    * Zone: DISCOM (ie: BRPL and BYPL) are decided to be the Zones of this model which will have the relation with NR region. 
     * Node: As mentioned, we have the generator for each Region (ie: NR, SR, WR, ER and NER) which then further connected to respective Generation Node (NR Generation, SR Generation, WR Generation, ER Generation and NER Generation), these generation nodes have the direct relation with NR region to compute Regional Generation of model.
3. Zone:
For Zone as of now 3 zones are designed as mentioned below:
     * BRPL Generation Zone: This Zone will have the connection with Total Generation node (Total Generation Node=NR Generation+ SR Generation+ WRGeneration+ ER Generation +NER Generation) and also will have the ZONE-to-ZONE relation with BRPL logic behind this was as the Generation zone will be catering the load of BRPL Zone.

    * BRPL: The BRPL zone will have the relation with the all the BRPL Grids and residing grid (like Inter DISCOM grids and Transco) and also BRPL Generation Lode.

    * BYPL: The BYPL zone will have the relation with the all the BYPL Grids and residing grid (like Inter DISCOM grids and Transco).

4. Nodes:
* Transco: All the Transco's are listed in this category with description as SAP
Functional Location ID.
* South: All the BRPL grids in South Circle is listed in this category with description as SAP Functional Location ID.
* West: All the BRPL Grid in West Circle is listed in this category with description as SAP Functional Location ID.
* Switching/Consumer: All the EHV consumers and Switching stations are listed in this category with description as SAP Functional Location ID.
* Inter-Discom: All the Inter-Discom region Grids that are connected to BRPL
Grids are mentioned in this category with description as SAP Functional
Location ID.
Line: All the Lines are listed in this category.
•TRF-Load: To link loading data to the LV Side of Transformers these Nodes are created and also in the description of these nodes the respective SCADA ID of
TRF is mentioned.
* T-OFF Points: Some Transmission Lines had T-OFF :
a. If the T-OFF point was directed by Grid means for example Line 220kV Okhla To DTC Central Workshop has route as First from 220kV Okhla to Okhla Ph-l Grid then From Okhla Ph-l Grid it is directed to DTC Central Workshop for these kind of case I made 2 different line.
        1) 220kV Okhla To DTC Central Workshop (220kV Okhla to Okhla Ph-l
        Grid)
        2) 220kV Okhla To DTC Central Workshop (Okhla Ph-l Grid-DTC
WORKSHOP)
b. If The T-OFF Point is directed by the DB (Distribution Box)so to illustrate that , Toff point nodes are created.
5. Lines:
Generation: Each Region (NR, SR, WR, ER and NER) has dedicated Generation node which is being connected to one Main Generation node and this Main Generation Node will have the membership to all Transco's.
The lines were a bit of the complicated class to implement in the model, the main problem was finding the equivalent TRX line between two grids being that in our network there is mostly mixed conductor use for example to join ITPO Grid to Exhibition Grid ,5 km length of conductor is used out of which 2 km is 3x400mm2 XLPE cable and 3 km is ACSR GOAT conductor.

For finding Equivalent Line following methodology is used:

a. Let assume we have 2 Conductors being C1 and C2
i. For C1: Resistance =R1, Reactance =X1, Ampacity=A1 ii. For C2: Resistance =R2, Reactance =X2, Ampacity=A2
For finding Max Flow: (PF is taken as 1 after analysis)
P = V3 * Ampacity * Volatge Level * PF
Therefore, For C1, Max Flow is M1 and For C2, Max Flow is M2

      Equivalent Line (Req + jXeq) = ((R1 + R2) + j(X1 + X2)) * Length of cable

      Equivalent Line (Max Flow) = Min(M1,M2)

and then they are converted to pu with 100 MVA base.

After the methodology was decided this analysis was done on the data received by EHV (Refer file: Source data/EHV Feeders List -June 2025-26.xls)

All the above logic is implemented and R, X and Max flow of each TR line is evaluated and Connection between each grid is made of respective circuit.

A separate Generation Category is also made in the Line class which contains all the lines that connecting the generation nodes of different generation node(regional wise) to main generation node and main generation node to all Transco's.

6. Transformer:
In every Grid Transformer is modelled and the From Node of transformer is connected to its respective grid and To Node is connected to it's respective TRF Load node.
Then to map the loading data with TRF the respective LV side SCADA ID is linked to TRF load node with decided bottom to top approach and also same SCADA ID linking is done to EHV Consumers.




















![Plexos Workflow](BRPL%20Plexos%20workflow.png)