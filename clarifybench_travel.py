# ===== clarifybench_travel.py: reads the flight routes DIRECTLY from ClarifyBench's own code =====
# (ClarifyBench must be cloned inside this folder: git clone https://github.com/MananSuri27/ClarifyBench.git)
import os, re

PLUGIN = os.path.join("ClarifyBench", "plugins", "travel_plugin.py")
source = open(PLUGIN, encoding="utf-8").read()

start = source.index("base_costs")                       # the route table inside ClarifyBench
end = source.index("}", start)
pairs = re.findall(r'\("([A-Z]{3})", "([A-Z]{3})"\):\s*(\d+)', source[start:end])

# All flights that exist, with their base price (USD). Not in this table = "No available route".
ROUTES = {(frm, to): int(price) for frm, to, price in pairs}

# Every airport that appears in the route table
AIRPORTS = sorted({airport for route in ROUTES for airport in route})


# City name -> airport code (ClarifyBench's own map, from get_nearest_airport_by_city)
start = source.index("airport_map = {")
end = source.index("}", start)
CITIES = dict(re.findall(r'"([^"]+)":\s*"([A-Z]{3})"', source[start:end]))