# Codebook for timeline events

Each event gets one theme, one valence and at most one anchor. Choose the theme that is the main subject of the event. If two themes fit, choose the more specific one.

## Themes

- ai_capability: AI reaches a level of skill, or its use spreads. AGI, superintelligence, AI agents, AI that matches or beats humans at tasks, AI in daily life. Use work_economy when the event is about jobs.
- ai_power: who controls AI and what AI controls. AI governance and rules, AI safety crises, AI takes power, AI and humans share or lose control, the singularity.
- work_economy: work, automation of jobs, the economy, wealth, inequality, post-scarcity, industry, mining.
- energy: energy sources and supply. Fusion, fission, solar, renewables, space-based power, end of fossil fuels.
- climate_environment: climate, emissions, warming, sea level, ecosystems, biodiversity, geoengineering, glacial cycles, habitability of Earth.
- health_longevity: medicine, disease, ageing, life expectancy, nanomedicine.
- genetics_enhancement: gene editing, genetic enhancement, designed children, humans that become different species or subspecies by biology.
- mind_digital: brain-computer interfaces, mind uploading, digital minds and their rights, virtual worlds, distributed consciousness.
- posthuman: humanity changes into something after humans. Transcendence, post-biological life, merging with machines, descendants that are no longer recognisably human. Use genetics_enhancement or mind_digital when the event names the method.
- population: population size, peak and decline, migration, cities and urbanisation.
- space_solar_system: the Moon, Mars, asteroids, orbital habitats, moons of other planets, settlements in the solar system, terraforming in the solar system.
- space_interstellar: probes or ships to other stars, settlements around other stars, colonisation of the galaxy or of other galaxies.
- megascale: Kardashev levels, Dyson spheres or swarms, engineering at the scale of stars or galaxies, artificial universes.
- extraterrestrial: search for life or intelligence elsewhere, detection, contact.
- war_conflict: wars, nuclear weapons, great-power rivalry, terrorism, armed conflict between settlements.
- catastrophe: pandemics, famines, collapse of civilisation, natural disasters (asteroid impact, supervolcano, solar storm), existential risk, extinction. Use war_conflict for wars and climate_environment for climate.
- governance: governments, world government, international agreements that are not about AI or climate, democracy, nations and borders.
- culture_society: language, religion, art, education, values, knowledge preservation, calendars, daily life, cities as places to live.
- science_knowledge: discoveries in science that are not a technology above. Physics, cosmology, understanding of the universe.
- outlook: a general statement about the state or the fate of humanity, with no single subject. Example: "Humanity's fate is uncertain."
- other: none of the above.

## Valence

From the point of view of humanity in general, as the event is written.

- positive: a gain, an achievement or a problem solved.
- negative: a loss, a harm, a danger or a failure.
- neutral: a change with no clear gain or loss, or a mix of both.

## Anchor

If the event is the same as one of these anchor events, give its id. If not, give null. The event must say the same thing, not only the same topic.

{anchors}
