import boto3
import json
import time

glue = boto3.client("glue", region_name="us-east-1")
crawler_name = "lab8-payments-crawler"
database_name = "lab8_crawled"

print(f"Waiting for crawler '{crawler_name}' to finish...")
start_time = time.time()

while True:
    resp = glue.get_crawler(Name=crawler_name)
    crawler = resp["Crawler"]
    state = crawler["State"]
    status = crawler.get("LastCrawl", {}).get("Status", "N/A")
    print(f"[{int(time.time() - start_time)}s] State: {state}, LastCrawl Status: {status}")
    if state == "READY":
        break
    time.sleep(10)

print(f"Crawler finished in {int(time.time() - start_time)}s.")

# List tables in crawled database
tables_resp = glue.get_tables(DatabaseName=database_name)
tables = tables_resp.get("TableList", [])
print(f"Tables found in {database_name}: {[t['Name'] for t in tables]}")

schema_info = {}
for t in tables:
    t_name = t["Name"]
    table_details = glue.get_table(DatabaseName=database_name, Name=t_name)["Table"]
    schema_info[t_name] = {
        "Columns": table_details.get("StorageDescriptor", {}).get("Columns", []),
        "PartitionKeys": table_details.get("PartitionKeys", []),
        "Parameters": table_details.get("Parameters", {}),
    }

with open("lab8/part2/results/glue_schema.json", "w", encoding="utf-8") as f:
    json.dump(schema_info, f, indent=2, ensure_ascii=False)

print("Schema saved to lab8/part2/results/glue_schema.json.")

# Delete the crawler as requested (keep nothing that bills)
glue.delete_crawler(Name=crawler_name)
print(f"Deleted crawler '{crawler_name}'.")
