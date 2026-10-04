[DefaultOutputDestinationSettings = [DestinationDefinition = [Kind = "Reference", QueryName = "DefaultDestination", IsNewTarget = true], UpdateMethod = [Kind = "Replace"], DestinationTypeSettings = [Kind = "Table"]], StagingDefinition = [Kind = "FastCopy"]]
section Section1;
shared DefaultDestination = Lakehouse.Contents([EnableFolding = false]){[workspaceId = "adcd77fd-65bc-4f6a-ad1d-e0b51a8dd578"]}[Data]{[lakehouseId = "c30e4d42-bff9-4054-85dc-9347c329fa92"]}[Data];
[BindToDefaultDestination = true]
shared fact_vaccine_inventory = let
  Source = Lakehouse.Contents([HierarchicalNavigation = null, EnableVorder = true, OutputMetadataRefresh = true]),
  #"Navigation 1" = Source{[workspaceId = "adcd77fd-65bc-4f6a-ad1d-e0b51a8dd578"]}[Data],
  #"Navigation 2" = #"Navigation 1"{[lakehouseId = "c30e4d42-bff9-4054-85dc-9347c329fa92"]}[Data],
  #"Navigation 3" = #"Navigation 2"{[Id = "Files", ItemKind = "Folder"]}[Data],
  Navigation = #"Navigation 3"{[Name = "phc_centres"]}[Content],
  #"Navigation 4" = Navigation{[Name = "data files"]}[Content],
  #"Navigation 5" = #"Navigation 4"{[Name = "vaccine_inventory.csv"]}[Content],
  #"Imported CSV" = Csv.Document(#"Navigation 5", [Delimiter = ",", Columns = 21, QuoteStyle = QuoteStyle.None]),
  #"Promoted headers" = Table.PromoteHeaders(#"Imported CSV", [PromoteAllScalars = true]),
  #"Changed column type" = Table.TransformColumnTypes(#"Promoted headers", {{"facility_id", type text}, {"vaccine_id", type text}, {"vaccine_name", type text}, {"vaccine_category", type text}, {"presentation", type text}, {"dose_volume", type text}, {"unit_of_measure", type text}, {"inventory_record_date", type date}, {"stock_level", Int64.Type}, {"minimum_stock_level", Int64.Type}, {"maximum_stock_level", Int64.Type}, {"average_monthly_consumption", Int64.Type}, {"days_of_stock_remaining", type number}, {"stock_status", type text}, {"last_restock_date", type date}, {"quantity_last_restocked", Int64.Type}, {"batch_number", type text}, {"expiry_date", type date}, {"cold_chain_required", type logical}, {"cold_chain_uptime_pct", type number}, {"temperature_excursion_count", Int64.Type}})
in
  #"Changed column type";
