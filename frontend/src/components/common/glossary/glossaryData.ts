/**
 * The jargon translator's dictionary.
 *
 * OWNER: Member 3. To add a term, add one entry to GLOSSARY. Nothing else needs to change:
 * <Term id="your_id"> works anywhere, and the glossary drawer lists it automatically.
 *
 * Writing rules for entries:
 *   plain  one or two sentences a neighbour would understand; no other jargon inside it
 *   why    why a farmer choosing a rotation should care
 *   also   the abbreviation or the scientist's name for it
 *
 * TODO (Member 3): multi-language entries (add `plain_es`, `why_es` and a language switch in
 *   useFieldShift), and a `say` field with a phonetic spelling for a read-aloud / voice mode.
 */

export type GlossaryTopic = "Satellites" | "Water" | "Soil" | "Weather" | "Rotation" | "This tool";

export interface GlossaryEntry {
  id: string;
  term: string;
  also?: string;
  topic: GlossaryTopic;
  plain: string;
  why: string;
}

export const GLOSSARY: GlossaryEntry[] = [
  // ---- satellites
  { id: "ndvi", term: "Vegetation greenness", also: "NDVI, Normalized Difference Vegetation Index", topic: "Satellites",
    plain: "A satellite measure of how much living green plant covers the ground. Near 0.1-0.2 is bare soil or dead stubble; 0.8 is a thick, healthy canopy.",
    why: "Low greenness in a rainy month means bare, unprotected soil. A dip in mid-season means the crop is under stress." },
  { id: "smap", term: "SMAP soil moisture", also: "Soil Moisture Active Passive", topic: "Satellites",
    plain: "A NASA satellite that senses how wet the top couple of inches of soil are, every two to three days. Each reading covers a square about 6 miles across.",
    why: "It shows when droughts start and whether there is moisture to plant into, but it averages over thousands of hectares, not your field." },
  { id: "root_zone_anomaly", term: "Root-zone moisture anomaly", also: "SMAP L4 / MERRA-2 root-zone wetness", topic: "Satellites",
    plain: "How much wetter or drier than normal the soil is where roots grow, for that time of year. Below -1 is a notably dry month.",
    why: "Counting dry months per year shows whether droughts are becoming more common where you farm." },
  { id: "gpm", term: "GPM IMERG rainfall", also: "Global Precipitation Measurement", topic: "Satellites",
    plain: "Rainfall measured from orbit every half hour, in squares about 6 miles across.",
    why: "It captures how hard it rains, not just how much, which is what moves soil. It can miss or exaggerate storms a gauge would catch." },
  { id: "ecostress", term: "ECOSTRESS", also: "land-surface temperature and plant water use", topic: "Satellites",
    plain: "A sensor on the Space Station that takes the temperature of the ground and plants in detail fine enough to see parts of a field.",
    why: "Plants short of water stop cooling themselves and heat up. Hot patches show where a crop is struggling." },
  { id: "lst", term: "Land-surface temperature", also: "LST, skin temperature", topic: "Satellites",
    plain: "How hot the ground or crop canopy itself is, not the air above it. Bare dry soil can run 20-30 degrees F hotter than the air.",
    why: "A cool surface means plants have water to evaporate. A hot one means dry, bare or stressed ground." },
  { id: "grace", term: "GRACE water storage", also: "GRACE-FO, terrestrial water storage", topic: "Satellites",
    plain: "Twin satellites that weigh all the water in a region, including deep groundwater, by sensing tiny changes in gravity. One reading covers an area about 200 miles across.",
    why: "It shows whether the regional aquifer is being drawn down faster than it refills. It cannot tell you about one well." },
  { id: "modis", term: "MODIS", also: "Moderate Resolution Imaging Spectroradiometer", topic: "Satellites",
    plain: "A NASA sensor that photographs the whole Earth almost daily in squares 250 metres to 1 km across, since 2000.",
    why: "Its long record shows a field's typical green-up, harvest and bare periods year after year." },
  { id: "resolution", term: "Pixel size", also: "spatial resolution", topic: "Satellites",
    plain: "The size of the square on the ground that one satellite reading covers. A 9 km pixel blends everything inside it into one number.",
    why: "When a pixel is much bigger than your field, the reading describes your neighbourhood, not your field." },
  { id: "srtm", term: "SRTM elevation", also: "Shuttle Radar Topography Mission", topic: "Satellites",
    plain: "A map of land height made by radar from the Space Shuttle, with a reading every 30 metres.",
    why: "Slope decides how fast water runs off and how much soil it takes with it." },

  // ---- water
  { id: "et", term: "Evapotranspiration", also: "ET", topic: "Water",
    plain: "The water that leaves a field as vapour: what evaporates from the soil plus what plants breathe out through their leaves.",
    why: "It is the field's water bill. A rotation that needs less of it leaves more in the soil or in the aquifer." },
  { id: "et0", term: "Reference evapotranspiration", also: "ET0, ETo", topic: "Water",
    plain: "How much water a well-watered lawn would use in your weather. It measures how thirsty the air is.",
    why: "Hotter, drier, windier weather raises it, so every crop needs more water to yield the same." },
  { id: "vpd", term: "Vapor pressure deficit", also: "VPD", topic: "Water",
    plain: "How much more moisture the air could hold. High on hot, dry afternoons.",
    why: "When it is high, crops lose water fast and may shut down growth even in moist soil." },
  { id: "water_stress", term: "Crop water stress", topic: "Water",
    plain: "The share of the water a crop wanted that the soil, rain and irrigation could not supply.",
    why: "Stress at flowering or grain fill costs yield directly. It is the number to watch in dry-year comparisons." },
  { id: "allocation", term: "Water allocation", topic: "Water",
    plain: "The amount of irrigation water you are allowed, or able, to pump in a year.",
    why: "When a rotation needs more than the allocation, the model shows the yield lost to the shortfall." },
  { id: "infiltration", term: "Infiltration", topic: "Water",
    plain: "Rain soaking into the soil instead of running off the surface.",
    why: "Water that soaks in grows the crop and refills the profile. Water that runs off takes soil and nutrients with it." },
  { id: "aridity", term: "Aridity index", also: "P / ET0", topic: "Water",
    plain: "Yearly rain divided by how much water the air could take up. Below about 0.5 is semi-arid.",
    why: "It tells you at a glance whether water or something else is the main limit on the farm." },
  { id: "fused_rain", term: "Fused rainfall", topic: "Water",
    plain: "One rainfall estimate blended from satellite, weather-model and rain-gauge records, trusting each in proportion to how well it matches the gauges here.",
    why: "No single source is right everywhere. Blending them, and showing how far apart they are, is more honest than picking one." },

  // ---- soil
  { id: "organic_matter", term: "Soil organic matter", also: "SOM, soil carbon", topic: "Soil",
    plain: "The dark, decayed plant and root material in topsoil. Most cropland has 1 to 5 percent.",
    why: "Each extra percent holds more water and nutrients and makes the soil easier to work. It builds slowly and is lost quickly." },
  { id: "hsg", term: "Hydrologic soil group", also: "HSG A, B, C, D", topic: "Soil",
    plain: "A soil-survey rating of how readily a soil takes in rain. A soaks it up like sand; D sheds it like clay or a soil with a shallow water table.",
    why: "On C and D soils, heavy rain becomes runoff, so ground cover matters most there." },
  { id: "awc", term: "Available water capacity", also: "AWC, plant-available water", topic: "Soil",
    plain: "How much water the root zone can hold in reach of plants, like the size of the soil's water tank.",
    why: "A big tank carries a crop through a dry spell and makes fallow or cover-crop water trade-offs smaller." },
  { id: "kw", term: "Erodibility", also: "K factor, Kw", topic: "Soil",
    plain: "How easily a soil's particles are detached and carried by rain and runoff. Silty soils are the most erodible.",
    why: "High erodibility on a slope is where bare months are most costly." },
  { id: "t_factor", term: "Tolerable soil loss", also: "T factor", topic: "Soil",
    plain: "The soil survey's estimate of how many tonnes of soil per hectare a field can lose each year and stay productive, usually about 7 to 11.",
    why: "Losing more than T means the topsoil is thinning faster than it forms." },
  { id: "rusle", term: "Erosion estimate", also: "RUSLE", topic: "Soil",
    plain: "A standard formula that estimates soil washed off a field from rain intensity, soil type, slope and how well the ground is covered.",
    why: "Cover is the one factor a farmer controls, which is why rotations change the answer so much." },
  { id: "soilgrids", term: "SoilGrids", also: "ISRIC SoilGrids 250 m", topic: "Soil",
    plain: "A global soil map made by machine learning from about 240,000 soil profiles and satellite data, at 250 m pixels.",
    why: "It covers every Malaysian field, but it is an estimate: peat and narrow sand ridges are often missed, so a DOA soil survey or a soil test beats it." },
  { id: "salinity", term: "Salinity", also: "EC, electrical conductivity", topic: "Soil",
    plain: "Dissolved salts in the soil, measured by how well the soil solution conducts electricity.",
    why: "Salts make it harder for roots to take up water. Some crops, like barley and cotton, tolerate much more than others." },
  { id: "living_roots", term: "Living roots", topic: "Soil",
    plain: "Months of the year when something is alive and growing in the field.",
    why: "Roots feed soil organisms, hold soil together and take up nitrogen that would otherwise leach." },

  // ---- weather
  { id: "gdd", term: "Growing degree days", also: "GDD, heat units", topic: "Weather",
    plain: "A running total of warmth above the temperature a crop needs to grow. Each crop needs a certain total to mature.",
    why: "It decides whether a crop can finish in your season, and it is how this tool works out planting and harvest months." },
  { id: "monsoon", term: "Monsoon seasons", also: "northeast and southwest monsoon", topic: "Weather",
    plain: "Malaysia is warm all year; the seasons are set by rain. The northeast monsoon (Nov-Mar) floods the east coast, the southwest monsoon (May-Sep) is drier.",
    why: "With no winter, planting dates follow the rains: this tool plants the first crop of the year at the start of the wettest window and chains the rest after it." },
  { id: "heat_days", term: "Heat days", topic: "Weather",
    plain: "Days when the temperature reaches 35 C (95 F) or more.",
    why: "Heat at flowering or grain fill cuts yield even with plenty of water. Some crops shrug it off; corn and peas do not." },
  { id: "erosive_rain", term: "Erosive rain", also: "rainfall erosivity, R factor", topic: "Weather",
    plain: "Rain heavy enough to splash and carry soil, counted here as days with more than half an inch.",
    why: "A few big storms do most of the erosion in a year, so what matters is whether the soil is covered when they come." },
  { id: "trend", term: "Trend", topic: "Weather",
    plain: "Whether something has been rising or falling over the 24-year record, and whether the change is clear or could be chance.",
    why: "A clear trend is a reason to plan for more of the same. An unclear one is a reason to stay flexible." },

  // ---- rotation
  { id: "cover_crop", term: "Cover crop", topic: "Rotation",
    plain: "A crop grown between cash crops to protect and feed the soil rather than to sell.",
    why: "It fills bare months, but it costs seed and management and, in dry places, some soil moisture." },
  { id: "nitrogen_fixation", term: "Nitrogen fixation", also: "legume credit", topic: "Rotation",
    plain: "Legumes such as soybeans, peas, clover and alfalfa host bacteria that turn nitrogen from the air into plant food.",
    why: "The next crop needs less purchased fertiliser. The size of the credit varies, so test before cutting rates." },
  { id: "pest_break", term: "Pest and disease break", topic: "Rotation",
    plain: "Years between growing the same crop, or its close relatives, in the same field.",
    why: "Many insects, nematodes and diseases survive only on their host. Without it for a year or more, their numbers fall." },
  { id: "functional_group", term: "Crop types", also: "functional groups", topic: "Rotation",
    plain: "Four broad kinds of crop: cool-season grasses, warm-season grasses, cool-season broadleaves and warm-season broadleaves.",
    why: "Mixing them changes planting dates, herbicides and rooting, which is what keeps weeds and pests off balance." },
  { id: "fallow", term: "Fallow", topic: "Rotation",
    plain: "Leaving a field unplanted for a season to store rain in the soil for the next crop.",
    why: "It steadies yields in dry country, but the soil sits bare, erodes and loses organic matter." },
  { id: "tillage", term: "Tillage system", also: "conventional, reduced, no-till", topic: "Rotation",
    plain: "How much the soil is worked. No-till plants straight into last year's residue; conventional tillage buries most of it.",
    why: "Residue on the surface is the cheapest erosion control there is, and it saves water by shading the soil." },
  { id: "green_bridge", term: "Green bridge", topic: "Rotation",
    plain: "A living plant that carries a disease or insect from one crop to the next.",
    why: "A cover crop related to the next cash crop can keep its pests alive through the off-season." },
  { id: "herbicide_carryover", term: "Herbicide carryover", topic: "Rotation",
    plain: "Weed killer from one crop that lingers in the soil long enough to injure the next crop.",
    why: "It is the most common way a new rotation crop fails in its first year. Check every label." },

  // ---- this tool
  { id: "fit_score", term: "Fit score", topic: "This tool",
    plain: "A 0-100 summary of how well a rotation matches the priorities you set, after subtracting points for new equipment, thin markets and the amount of change.",
    why: "It ranks options for your goals. Move the sliders and it changes, because what is best depends on what you value." },
  { id: "confidence", term: "Confidence", topic: "This tool",
    plain: "How much to trust a result, from how good the data is for this field and how well a simple model can answer that question at all.",
    why: "When two options differ by less than the uncertainty shown, treat them as a tie and decide on other grounds." },
  { id: "provenance", term: "Data badges", also: "Live, Curated, Stand-in, Modelled", topic: "This tool",
    plain: "A tag on each number saying whether it was pulled live for this field, assembled from published sources, borrowed from a related product, or computed.",
    why: "Numbers that were measured here deserve more trust than numbers that were looked up or estimated." },
  { id: "baseline", term: "Current rotation", also: "baseline", topic: "This tool",
    plain: "What the field grows now. Every alternative is measured against it with the same models.",
    why: "If the baseline is wrong, every comparison is off. Correct it first." },
  { id: "bad_year", term: "Bad-year income", also: "1-in-5 year", topic: "This tool",
    plain: "The net return in a poor year, the kind that comes about once in five, found by replaying 2001-2024 weather through the rotation.",
    why: "A rotation with a lower average but a better bad year may let the farm sleep easier." },
  { id: "stress_test", term: "Stress test", also: "what-if scenario", topic: "This tool",
    plain: "Re-running the rotations with the weather shifted: hotter, drier, stormier or with less irrigation water.",
    why: "It shows which option holds up if conditions keep changing. It is a test, not a forecast." },
];

export const GLOSSARY_BY_ID: Record<string, GlossaryEntry> = Object.fromEntries(GLOSSARY.map((g) => [g.id, g]));
export const GLOSSARY_TOPICS: GlossaryTopic[] = ["Satellites", "Water", "Soil", "Weather", "Rotation", "This tool"];
