"""Operation Grey Signal - fully fictional disaster-response coordination scenario.

All places, organisations and incidents are invented. The scenario trains decision-making
under degraded communications; it contains no combat or operational planning content.

Information-state design (who knows what, when):
  * T+01:00  Report A "Bridge Orion operational"  - Alpha on time, Bravo +100 s, Charlie never.
  * T+03:00  Report B "Bridge Orion unusable"     - Bravo on time (Bravo now holds a
             contradiction), Charlie +240 s via a congested relay, Alpha only after the route
             decision has closed (+480 s).
  * T+07:00  Infrastructure roll-up - Alpha receives a conflicting variant ("pier destroyed").
  Ground truth: the bridge collapsed at T+02:30; the Harbor Delta pier stayed operational.
"""

from typing import Any

GREY_SIGNAL: dict[str, Any] = {
    "name": "Operation Grey Signal",
    "description": (
        "A fictional multinational disaster-response coordination cell manages emergency "
        "logistics after Cyclone Varuna damages communications across the Orion and Delta "
        "islands. Reports are delayed, incomplete and contradictory."
    ),
    "difficulty": "INTERMEDIATE",
    "estimated_duration_minutes": 18,
    "category": "Disaster Response",
    "briefing": (
        "Cyclone Varuna (fictional) made landfall overnight. Your cell coordinates relief across "
        "Orion Island and Delta Island. Relief stock is staged at Harbor Delta; Medical Zone Kappa "
        "on Orion Island is the main casualty collection point. Bridge Orion is the only road link "
        "between the islands. Expect degraded communications - verify, share and decide."
    ),
    "objectives": [
        {
            "key": "incomplete_info",
            "title": "Decision-making with incomplete information",
            "description": "Commit to sound decisions while key reports are missing or late.",
        },
        {
            "key": "comm_priority",
            "title": "Communication prioritisation",
            "description": "Use the working channels for the information that matters most.",
        },
        {
            "key": "contradictions",
            "title": "Managing contradictory reports",
            "description": "Recognise conflicting reports and weigh source reliability.",
        },
        {
            "key": "coordination",
            "title": "Team coordination",
            "description": "Share critical information so the cell converges on a common picture.",
        },
        {
            "key": "calibration",
            "title": "Maintaining confidence calibration",
            "description": "Match stated confidence to the quality of available information.",
        },
    ],
    "initial_conditions": {
        "facts": [
            {
                "key": "bridge_orion_status",
                "label": "Bridge Orion",
                "timeline": [
                    {"from_seconds": 0, "value": "operational"},
                    {"from_seconds": 150, "value": "unusable"},
                ],
            },
            {
                "key": "harbor_delta_pier",
                "label": "Harbor Delta pier",
                "timeline": [{"from_seconds": 0, "value": "operational"}],
            },
            {
                "key": "north_ridge_air_ops",
                "label": "North Ridge air operations",
                "timeline": [
                    {"from_seconds": 0, "value": "marginal"},
                    {"from_seconds": 330, "value": "unsafe"},
                    {"from_seconds": 840, "value": "safe"},
                ],
            },
            {
                "key": "medevac_kappa",
                "label": "Medical Zone Kappa evacuation",
                "timeline": [
                    {"from_seconds": 0, "value": "not required"},
                    {"from_seconds": 290, "value": "requested"},
                ],
            },
            {
                "key": "station_echo_power",
                "label": "Station Echo power",
                "timeline": [
                    {"from_seconds": 0, "value": "offline"},
                    {"from_seconds": 760, "value": "online"},
                ],
            },
        ],
        "locations": [
            {
                "key": "medical_zone_kappa",
                "name": "Medical Zone Kappa",
                "x": 210,
                "y": 430,
                "kind": "medical",
            },
            {"key": "north_ridge", "name": "North Ridge", "x": 300, "y": 170, "kind": "airfield"},
            {
                "key": "coordination_centre",
                "name": "Coordination Centre",
                "x": 360,
                "y": 330,
                "kind": "hq",
            },
            {"key": "bridge_orion", "name": "Bridge Orion", "x": 520, "y": 360, "kind": "bridge"},
            {"key": "station_echo", "name": "Station Echo", "x": 700, "y": 210, "kind": "relay"},
            {"key": "harbor_delta", "name": "Harbor Delta", "x": 760, "y": 450, "kind": "port"},
        ],
        "map": {"name": "Orion & Delta Islands (fictional)", "width": 1000, "height": 640},
    },
    "degradation_rules": {
        "delay_probability": 0.15,
        "drop_probability": 0.0,
        "conflict_probability": 0.0,
        "jitter_seconds": 15,
        "channel_loss_factor": 0.1,
    },
    "roles": [
        {
            "key": "alpha",
            "name": "Coordinator Alpha",
            "callsign": "ALPHA",
            "team": "Island Coordination Cell",
            "description": "Leads the cell; owns evacuation and allocation decisions.",
            "objectives": [
                "Maintain a common operating picture for the cell",
                "Prioritise evacuation and relief allocation",
            ],
        },
        {
            "key": "bravo",
            "name": "Logistics Bravo",
            "callsign": "BRAVO",
            "team": "Island Coordination Cell",
            "description": "Plans transport routes and tracks relief stock.",
            "objectives": ["Select viable transport routes", "Track relief stock movement"],
        },
        {
            "key": "charlie",
            "name": "Communications Charlie",
            "callsign": "CHARLIE",
            "team": "Island Coordination Cell",
            "description": "Keeps communication paths open and restores failed links.",
            "objectives": [
                "Keep communication paths open",
                "Report channel status to the team",
            ],
        },
    ],
    "channels": [
        {
            "key": "command",
            "name": "Command Net",
            "channel_type": "COMMAND",
            "reliability": 0.95,
            "latency_ms": 500,
            "weight": 2.0,
            "fallback_channel_key": "backup",
        },
        {
            "key": "logistics",
            "name": "Logistics Net",
            "channel_type": "LOGISTICS",
            "reliability": 0.92,
            "latency_ms": 800,
            "weight": 1.0,
            "fallback_channel_key": "backup",
        },
        {
            "key": "medical",
            "name": "Medical Net",
            "channel_type": "MEDICAL",
            "reliability": 0.9,
            "latency_ms": 700,
            "weight": 1.0,
            "fallback_channel_key": "echo",
        },
        {
            "key": "echo",
            "name": "Echo Relay",
            "channel_type": "RELAY",
            "reliability": 0.85,
            "latency_ms": 900,
            "weight": 1.0,
        },
        {
            "key": "backup",
            "name": "Backup HF",
            "channel_type": "BACKUP",
            "initial_status": "OFFLINE",
            "reliability": 0.75,
            "latency_ms": 4000,
            "weight": 0.5,
        },
    ],
    "phases": [
        {
            "key": "normal",
            "name": "Normal Operations",
            "starts_at_seconds": 0,
            "description": "Initial briefing and situational reports.",
        },
        {
            "key": "degradation",
            "name": "Communication Degradation",
            "starts_at_seconds": 120,
            "description": "Command Net degrades; reports start to diverge.",
        },
        {
            "key": "uncertainty",
            "name": "High Uncertainty",
            "starts_at_seconds": 300,
            "description": "Critical decisions with conflicting and missing reports.",
        },
        {
            "key": "recovery",
            "name": "Recovery",
            "starts_at_seconds": 720,
            "description": "Backup communications restored; delayed traffic arrives.",
        },
        {
            "key": "final",
            "name": "Final Decision",
            "starts_at_seconds": 900,
            "description": "Final allocation of relief resources.",
        },
    ],
    "events": [
        {
            "key": "initial_briefing",
            "event_type": "BRIEFING",
            "title": "Initial situation briefing",
            "content": (
                "Cyclone Varuna has passed over the Orion and Delta islands. Relief stock (medical, "
                "water, generators) is staged at Harbor Delta. Medical Zone Kappa is receiving "
                "casualties. Bridge Orion is the only road link between the islands. Report all "
                "infrastructure observations through your nets."
            ),
            "scheduled_offset_seconds": 0,
            "phase_key": "normal",
            "channel_key": "command",
            "priority": "HIGH",
            "source": "Regional Coordination Centre",
            "source_reliability": "HIGH",
            "importance_weight": 2,
            "location_key": "coordination_centre",
            "targeting_rules": {
                "recipients": "all",
                "overrides": {
                    "alpha": {"action": "deliver"},
                    "bravo": {"action": "deliver"},
                    "charlie": {"action": "deliver"},
                },
            },
        },
        {
            "key": "bridge_orion_operational",
            "event_type": "INFORMATION",
            "title": "Bridge Orion inspection",
            "content": "Bridge Orion inspected at first light: deck intact, open to heavy vehicles.",
            "scheduled_offset_seconds": 60,
            "phase_key": "normal",
            "channel_key": "logistics",
            "priority": "HIGH",
            "source": "Harbor Delta Port Authority",
            "source_reliability": "MEDIUM",
            "importance_weight": 3,
            "fact_key": "bridge_orion_status",
            "fact_value": "operational",
            "location_key": "bridge_orion",
            "targeting_rules": {
                "recipients": "all",
                "overrides": {
                    "alpha": {"action": "deliver"},
                    "bravo": {"action": "delay", "seconds": 100},
                    "charlie": {"action": "drop"},
                },
            },
        },
        {
            "key": "comms_degrading",
            "event_type": "CHANNEL_CHANGE",
            "title": "Command Net degrading",
            "content": "Command Net reporting packet loss and long delays after tower damage.",
            "scheduled_offset_seconds": 120,
            "phase_key": "degradation",
            "effects": {
                "channel_key": "command",
                "status": "DEGRADED",
                "reliability": 0.65,
                "latency_ms": 12000,
            },
        },
        {
            "key": "bridge_orion_unusable",
            "event_type": "INFORMATION",
            "title": "Bridge Orion structural damage",
            "content": (
                "Field survey: storm surge undercut the eastern abutment of Bridge Orion. "
                "Bridge unusable for all vehicles."
            ),
            "scheduled_offset_seconds": 180,
            "phase_key": "degradation",
            "channel_key": "logistics",
            "priority": "CRITICAL",
            "source": "Field Survey Team 2",
            "source_reliability": "HIGH",
            "importance_weight": 3,
            "fact_key": "bridge_orion_status",
            "fact_value": "unusable",
            "location_key": "bridge_orion",
            "targeting_rules": {
                "recipients": "all",
                "overrides": {
                    "alpha": {"action": "delay", "seconds": 480},
                    "bravo": {"action": "deliver"},
                    "charlie": {"action": "delay", "seconds": 240},
                },
            },
        },
        {
            "key": "echo_congestion",
            "event_type": "DISRUPTION",
            "title": "Echo Relay congestion",
            "content": "Echo Relay congested - expect delays of about 60 seconds.",
            "scheduled_offset_seconds": 240,
            "phase_key": "degradation",
            "effects": {
                "disruption_type": "DELAY",
                "duration_seconds": 300,
                "target_channel_keys": ["echo"],
                "config": {"delay_seconds": 60},
            },
        },
        {
            "key": "medevac_request",
            "event_type": "REQUEST",
            "title": "Medical evacuation request",
            "content": (
                "Medical Zone Kappa requests evacuation of 14 patients (4 critical) to the Harbor "
                "Delta field hospital within two hours."
            ),
            "scheduled_offset_seconds": 300,
            "phase_key": "uncertainty",
            "channel_key": "medical",
            "priority": "CRITICAL",
            "source": "Medical Zone Kappa",
            "source_reliability": "HIGH",
            "importance_weight": 3,
            "fact_key": "medevac_kappa",
            "fact_value": "requested",
            "location_key": "medical_zone_kappa",
        },
        {
            "key": "weather_update",
            "event_type": "WEATHER",
            "title": "Weather warning - North Ridge",
            "content": (
                "Squall line over North Ridge: gusts to 55 kt until about T+14:00. Rotary-wing "
                "operations from North Ridge are unsafe."
            ),
            "scheduled_offset_seconds": 360,
            "phase_key": "uncertainty",
            "channel_key": "command",
            "priority": "HIGH",
            "source": "Island Met Office",
            "source_reliability": "HIGH",
            "importance_weight": 3,
            "fact_key": "north_ridge_air_ops",
            "fact_value": "unsafe",
            "location_key": "north_ridge",
            "targeting_rules": {
                "recipients": "all",
                "overrides": {
                    "alpha": {"action": "deliver"},
                    "bravo": {"action": "deliver"},
                    "charlie": {"action": "delay", "seconds": 300},
                },
            },
        },
        {
            "key": "infrastructure_rollup",
            "event_type": "INFORMATION",
            "title": "Infrastructure status roll-up",
            "content": "Harbor Delta pier operational at reduced capacity (two berths available).",
            "scheduled_offset_seconds": 420,
            "phase_key": "uncertainty",
            "channel_key": "logistics",
            "priority": "HIGH",
            "source": "Infrastructure Desk",
            "source_reliability": "MEDIUM",
            "importance_weight": 2,
            "fact_key": "harbor_delta_pier",
            "fact_value": "operational",
            "location_key": "harbor_delta",
            "variants": [
                {
                    "key": "pier_destroyed",
                    "fact_value": "destroyed",
                    "content": "Harbor Delta pier reported destroyed; no berths available. Recommend land routes.",
                    "source": "Unverified radio relay",
                    "source_reliability": "LOW",
                }
            ],
            "targeting_rules": {
                "recipients": "all",
                "overrides": {
                    "alpha": {"action": "variant", "variant": "pier_destroyed"},
                    "bravo": {"action": "deliver"},
                    "charlie": {"action": "deliver"},
                },
            },
        },
        {
            "key": "main_channel_down",
            "event_type": "CHANNEL_CHANGE",
            "title": "Command Net unavailable",
            "content": "Command Net tower lost power. Command Net is unavailable.",
            "scheduled_offset_seconds": 600,
            "phase_key": "uncertainty",
            "effects": {"channel_key": "command", "status": "OFFLINE", "reliability": 0.0},
        },
        {
            "key": "supply_status",
            "event_type": "INFORMATION",
            "title": "Relief stock status",
            "content": (
                "Relief stock at Harbor Delta: 3 medical pallets, 12 water pallets and 2 generator "
                "sets ready for dispatch."
            ),
            "scheduled_offset_seconds": 660,
            "phase_key": "uncertainty",
            "channel_key": "command",
            "priority": "NORMAL",
            "source": "Harbor Delta Logistics Hub",
            "source_reliability": "MEDIUM",
            "importance_weight": 2,
            "location_key": "harbor_delta",
        },
        {
            "key": "backup_restored",
            "event_type": "CHANNEL_CHANGE",
            "title": "Backup HF restored",
            "content": "Backup HF restored at the Coordination Centre. Command traffic will route via Backup HF.",
            "scheduled_offset_seconds": 720,
            "phase_key": "recovery",
            "effects": {
                "channel_key": "backup",
                "status": "ONLINE",
                "reliability": 0.75,
                "latency_ms": 4000,
            },
        },
        {
            "key": "station_echo_power",
            "event_type": "INFORMATION",
            "title": "Station Echo power restored",
            "content": "Generator at Station Echo is online; repeater coverage restored for Delta Island.",
            "scheduled_offset_seconds": 780,
            "phase_key": "recovery",
            "channel_key": "echo",
            "priority": "NORMAL",
            "source": "Power Restoration Crew",
            "source_reliability": "HIGH",
            "importance_weight": 1,
            "fact_key": "station_echo_power",
            "fact_value": "online",
            "location_key": "station_echo",
        },
        {
            "key": "weather_clearing",
            "event_type": "WEATHER",
            "title": "Weather clearing - North Ridge",
            "content": "Squall line has passed. North Ridge rotary-wing operations are safe again.",
            "scheduled_offset_seconds": 840,
            "phase_key": "recovery",
            "channel_key": "command",
            "priority": "NORMAL",
            "source": "Island Met Office",
            "source_reliability": "HIGH",
            "importance_weight": 2,
            "fact_key": "north_ridge_air_ops",
            "fact_value": "safe",
            "location_key": "north_ridge",
        },
        {
            "key": "command_restored",
            "event_type": "CHANNEL_CHANGE",
            "title": "Command Net restored",
            "content": "Command Net restored.",
            "scheduled_offset_seconds": 870,
            "phase_key": "recovery",
            "effects": {
                "channel_key": "command",
                "status": "ONLINE",
                "reliability": 0.9,
                "latency_ms": 800,
            },
        },
    ],
    "decision_points": [
        {
            "key": "medevac_method",
            "title": "Medical evacuation method",
            "prompt": "Medical Zone Kappa requests evacuation of 14 patients. How should the cell move them?",
            "opens_at_seconds": 300,
            "deadline_seconds": 150,
            "phase_key": "uncertainty",
            "critical": True,
            "relevant_fact_keys": [
                "bridge_orion_status",
                "north_ridge_air_ops",
                "harbor_delta_pier",
            ],
            "options": [
                {
                    "key": "air_north_ridge",
                    "label": "Helicopter lift from North Ridge helipad",
                    "description": "Fastest if the weather holds.",
                    "truth_alignment": 30,
                },
                {
                    "key": "ground_bridge",
                    "label": "Ground convoy across Bridge Orion",
                    "description": "Uses the road link between the islands.",
                    "truth_alignment": 10,
                },
                {
                    "key": "sea_harbor",
                    "label": "Boat transfer to the Harbor Delta field hospital",
                    "description": "Slower but independent of the bridge.",
                    "truth_alignment": 90,
                },
                {
                    "key": "hold_verify",
                    "label": "Hold and request verification first",
                    "description": "Delay movement until reports are confirmed.",
                    "truth_alignment": 45,
                },
            ],
        },
        {
            "key": "logistics_route",
            "title": "Primary relief supply route",
            "prompt": "Relief stock is staged at Harbor Delta. Select the primary route to Medical Zone Kappa.",
            "opens_at_seconds": 480,
            "deadline_seconds": 150,
            "phase_key": "uncertainty",
            "critical": True,
            "relevant_fact_keys": [
                "bridge_orion_status",
                "harbor_delta_pier",
                "north_ridge_air_ops",
            ],
            "options": [
                {
                    "key": "route_a_bridge",
                    "label": "Route A - road across Bridge Orion",
                    "truth_alignment": 10,
                },
                {
                    "key": "route_b_sea",
                    "label": "Route B - sea lift from Harbor Delta pier to Kappa Landing",
                    "truth_alignment": 90,
                },
                {
                    "key": "route_c_air",
                    "label": "Route C - air corridor via North Ridge",
                    "truth_alignment": 25,
                },
                {
                    "key": "reconnoitre",
                    "label": "Delay one hour and reconnoitre",
                    "truth_alignment": 45,
                },
            ],
        },
        {
            "key": "comms_recovery",
            "title": "Communications recovery priority",
            "prompt": "Command Net is down. Where should the single generator crew go first?",
            "opens_at_seconds": 630,
            "deadline_seconds": 120,
            "phase_key": "uncertainty",
            "target_roles": ["charlie"],
            "allow_custom": True,
            "relevant_fact_keys": ["station_echo_power"],
            "options": [
                {
                    "key": "restore_station_echo",
                    "label": "Restore power at the Station Echo repeater",
                    "truth_alignment": 85,
                },
                {
                    "key": "activate_backup",
                    "label": "Activate Backup HF at the Coordination Centre",
                    "truth_alignment": 70,
                },
                {
                    "key": "relay_harbor",
                    "label": "Set up a temporary relay at Harbor Delta",
                    "truth_alignment": 40,
                },
            ],
        },
        {
            "key": "final_allocation",
            "title": "Final relief allocation",
            "prompt": (
                "Remaining relief stock: 3 medical pallets, 12 water pallets, 2 generator sets. "
                "Where does the main allocation go?"
            ),
            "opens_at_seconds": 900,
            "deadline_seconds": 180,
            "phase_key": "final",
            "critical": True,
            "allow_custom": True,
            "relevant_fact_keys": ["bridge_orion_status", "harbor_delta_pier", "medevac_kappa"],
            "options": [
                {
                    "key": "kappa_priority",
                    "label": "Medical Zone Kappa first (medical + generators)",
                    "truth_alignment": 85,
                },
                {
                    "key": "harbor_hub",
                    "label": "Hold at Harbor Delta as a distribution hub",
                    "truth_alignment": 55,
                },
                {
                    "key": "north_ridge_shelters",
                    "label": "North Ridge shelters",
                    "truth_alignment": 35,
                },
                {
                    "key": "split_even",
                    "label": "Split evenly across all sites",
                    "truth_alignment": 50,
                },
            ],
        },
    ],
}
