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
* BRPL Generation Zone: This Zone will have the connection with Total
Generation node (Total Generation Node=NR Generation+ SR Generation+ WR
Generation+ ER Generation +NER Generation) and also will have the ZONE-to-ZONE relation with BRPL logic behind this was as the Generation zone will be catering the load of BRPL Zone.
BRPL: The BRPL zone will have the relation with the all the BRPL Grids and residing grid (like Inter DISCOM grids and Transco) and also BRPL Generation Lone.
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
![Plexos Workflow](BRPL%20Plexos%20workflow.png)