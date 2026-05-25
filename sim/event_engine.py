from __future__ import annotations

from dataclasses import replace
from .models import Driver, Race, RunningCar, RaceEvent
import random


BASE_POINTS = {
    1: 40, 2: 35, 3: 34, 4: 33, 5: 32, 6: 31, 7: 30, 8: 29, 9: 28, 10: 27,
    11: 26, 12: 25, 13: 24, 14: 23, 15: 22, 16: 21, 17: 20, 18: 19, 19: 18, 20: 17,
    21: 16, 22: 15, 23: 14, 24: 13, 25: 12, 26: 11, 27: 10, 28: 9, 29: 8, 30: 7,
    31: 6, 32: 5, 33: 4, 34: 3, 35: 2, 36: 1,
}

STAGE_POINTS = {
    1: 10, 2: 9, 3: 8, 4: 7, 5: 6,
    6: 5, 7: 4, 8: 3, 9: 2, 10: 1,
}

TRACK_WEIGHTS = {
    "short": {
        "speed": 0.25,
        "consistency": 0.20,
        "aggression": 0.25,
        "tire_saving": 0.10,
        "pit_crew": 0.20,
    },
    "speedway": {
        "speed": 0.35,
        "consistency": 0.20,
        "aggression": 0.15,
        "tire_saving": 0.15,
        "pit_crew": 0.15,
    },
    "superspeedway": {
        "speed": 0.20,
        "consistency": 0.15,
        "aggression": 0.30,
        "tire_saving": 0.05,
        "pit_crew": 0.30,
    },
    "road": {
        "speed": 0.30,
        "consistency": 0.30,
        "aggression": 0.10,
        "tire_saving": 0.20,
        "pit_crew": 0.10,
    },
}

INCIDENT_TEMPLATES = {
    "single_car_spin": [
        "{a} gets loose off Turn 4 and spins to bring out the caution.",
        "{a} loops it while fighting for track position.",
        "{a} snaps sideways on corner exit and the yellow is out.",
    ],
    "multi_car_crash": [
        "{a} and {b} make contact racing for position, collecting {c}.",
        "Big stack-up as {a} checks up and {b} piles in.",
        "{a} gets turned across traffic and several cars are involved.",
    ],
    "tire_failure": [
        "{a} cuts a tire and slaps the outside wall.",
        "Tire failure for {a}; debris is scattered across the racing groove.",
        "{a} blows a tire entering the corner and brings out the caution.",
    ],
    "mechanical": [
        "{a} slows with a mechanical issue and stops on track.",
        "Mechanical failure for {a}; race control throws the caution.",
        "{a} loses power and cannot make it back to pit road.",
    ],
    "debris": [
        "Debris has been spotted in the racing groove.",
        "Race control calls a debris caution.",
        "A piece of bodywork on the track forces a yellow.",
    ],
    "aggressive_contact": [
        "{a} sends it deep and makes contact with {b}.",
        "{a} leans on {b} too hard, triggering a caution.",
        "{a} and {b} clash after several laps of hard racing.",
    ],
}


class RaceSession:
    """
    Event-driven race session used by the Streamlit UI.

    Includes:
    - playable qualifying
    - lap-by-lap advancing
    - advance-until-next-event
    - cautions and crash narratives
    - damage penalties
    - fuel and tire consequences
    - manual pitting
    - manual retire / black flag
    - stage points
    """

    def __init__(
        self,
        race: Race,
        drivers: list[Driver],
        seed: int | None = None,
        chaos_override: int | None = None,
    ):
        self.race = replace(race, chaos=chaos_override) if chaos_override is not None else race
        self.drivers = list(drivers)
        self.random = random.Random(seed)

        self.current_lap = 0
        self.flag = "PRE_RACE"
        self.pit_road_open = False
        self.finished = False
        self.event_log: list[RaceEvent] = []

        self.last_positions: dict[str, int] = {}
        self.position_history: list[dict] = []

        self.field_aggression_modifier = 0.0
        self.caution_modifier = 0.0
        self.restart_intensity = 0.0
        self.race_control_strictness = 0.0

        # Qualifying state.
        self.qualifying_started = False
        self.qualifying_complete = False
        self.qualifying_queue: list[Driver] = []
        self.qualifying_results: list[dict] = []
        self.qualifying_positions: dict[str, int] | None = None

        # Build an initial grid automatically so race mode works even if the user skips qualifying.
        self.qualifying_positions = self._qualify(self.drivers)
        self.cars: list[RunningCar] = []
        self._build_cars_from_grid(self.qualifying_positions)

    # ------------------------------------------------------------------
    # Qualifying
    # ------------------------------------------------------------------

    def start_qualifying(self) -> RaceEvent:
        self.qualifying_started = True
        self.qualifying_complete = False
        self.qualifying_results = []

        # Randomize the qualifying run order so it feels like a session.
        self.qualifying_queue = list(self.drivers)
        self.random.shuffle(self.qualifying_queue)

        self.flag = "QUALIFYING"

        return self._event(
            "QUALIFYING",
            "Qualifying started",
            "Cars are ready to make qualifying attempts one at a time.",
        )

    def run_next_qualifier(self) -> RaceEvent:
        if not self.qualifying_started:
            return self.start_qualifying()

        if self.qualifying_complete:
            return self._event(
                "QUALIFYING",
                "Qualifying already complete",
                "The starting grid has already been set.",
                data={"grid": self.qualifying_results},
            )

        if not self.qualifying_queue:
            return self.finalize_qualifying()

        driver = self.qualifying_queue.pop(0)

        # Two-lap style qualifying attempt.
        lap_1 = (
            driver.qualifying * 0.50
            + driver.speed * 0.20
            + driver.consistency * 0.10
            + self.random.gauss(0, 14)
        )

        lap_2 = (
            driver.qualifying * 0.50
            + driver.speed * 0.20
            + driver.consistency * 0.10
            + self.random.gauss(0, 14)
        )

        best_lap = max(lap_1, lap_2)
        average_lap = (lap_1 + lap_2) / 2

        score = (best_lap * 0.70) + (average_lap * 0.30)

        self.qualifying_results.append(
            {
                "Driver ID": driver.driver_id,
                "Driver": driver.name,
                "Car": driver.car_number,
                "Team": driver.team,
                "Manufacturer": driver.manufacturer,
                "Lap 1": round(lap_1, 3),
                "Lap 2": round(lap_2, 3),
                "Best Lap": round(best_lap, 3),
                "Qualifying Score": round(score, 3),
            }
        )

        self._rank_qualifying_results()

        current_rank = next(
            row["Rank"]
            for row in self.qualifying_results
            if row["Driver ID"] == driver.driver_id
        )

        provisional_pole = self.qualifying_results[0]["Driver"]

        if not self.qualifying_queue:
            self.finalize_qualifying()
            return self._event(
                "QUALIFYING",
                "Qualifying complete",
                f"{driver.name} completed their run and qualified P{current_rank}. Provisional pole: {provisional_pole}. The grid is now locked.",
                data={"driver": driver.name, "rank": current_rank, "grid": self.qualifying_results},
            )

        return self._event(
            "QUALIFYING",
            "Qualifying run complete",
            f"{driver.name} completed their run and is currently P{current_rank}. Provisional pole: {provisional_pole}.",
            data={"driver": driver.name, "rank": current_rank, "grid": self.qualifying_results},
        )

    def run_all_qualifying(self) -> RaceEvent:
        if not self.qualifying_started:
            self.start_qualifying()

        while self.qualifying_queue:
            self.run_next_qualifier()

        return self.finalize_qualifying()

    def finalize_qualifying(self) -> RaceEvent:
        if not self.qualifying_results:
            self.qualifying_positions = self._qualify(self.drivers)
        else:
            self._rank_qualifying_results()
            self.qualifying_positions = {
                row["Driver ID"]: row["Rank"]
                for row in self.qualifying_results
            }

        self.qualifying_complete = True
        self.flag = "PRE_RACE"
        self._build_cars_from_grid(self.qualifying_positions)

        pole = self.running_order()[0].driver.name if self.running_order() else "No pole sitter"

        return self._event(
            "QUALIFYING",
            "Grid locked",
            f"Qualifying is complete. {pole} wins the pole.",
            data={"pole": pole, "grid": self.qualifying_results},
        )

    def qualifying_snapshot(self) -> list[dict]:
        self._rank_qualifying_results()
        return list(self.qualifying_results)

    def _rank_qualifying_results(self) -> None:
        self.qualifying_results.sort(
            key=lambda row: row["Qualifying Score"],
            reverse=True,
        )

        for index, row in enumerate(self.qualifying_results, start=1):
            row["Rank"] = index

    # ------------------------------------------------------------------
    # Public race controls
    # ------------------------------------------------------------------

    def advance_one_lap(self) -> RaceEvent:
        if self.finished:
            return self._event("RACE_FINISH", "Race already complete", "The race has already finished.")

        if self.flag == "QUALIFYING":
            return self._event(
                "QUALIFYING",
                "Qualifying in progress",
                "Finish or finalize qualifying before starting the race.",
            )

        if self.flag == "PRE_RACE":
            self.flag = "GREEN"
            return self._event("GREEN_FLAG", "Green flag", f"{self.race.name} is underway at {self.race.track}.")

        if self.flag == "RED":
            return self._event(
                "RACE_CONTROL",
                "Race is red flagged",
                "The race is stopped. Resume the race before advancing laps.",
                requires_decision=True,
                options=["resume_race"],
            )

        self.current_lap += 1
        fuel_event = self._run_green_lap()
        self._sort_field()
        self._record_position_history()

        if fuel_event:
            return fuel_event

        if self.current_lap >= self.race.laps:
            self.finished = True
            return self._finish_event()

        incident = self._maybe_incident()
        if incident:
            return incident

        if self.current_lap in (self.race.stage_1_end, self.race.stage_2_end):
            return self._stage_end_event()

        if self._is_pit_window():
            return self._pit_window_event()

        return self._event(
            "LAP_COMPLETE",
            f"Lap {self.current_lap} complete",
            f"Lap {self.current_lap} is complete. The race remains green.",
        )

    def run_until_next_action(self) -> RaceEvent:
        if self.finished:
            return self._event("RACE_FINISH", "Race already complete", "The race has already finished.")

        if self.flag == "QUALIFYING":
            return self._event(
                "QUALIFYING",
                "Qualifying in progress",
                "Finish or finalize qualifying before starting the race.",
            )

        if self.flag == "PRE_RACE":
            self.flag = "GREEN"
            return self._event("GREEN_FLAG", "Green flag", f"{self.race.name} is underway at {self.race.track}.")

        if self.flag == "RED":
            return self._event(
                "RACE_CONTROL",
                "Race is red flagged",
                "The race is stopped. Resume the race before advancing.",
                requires_decision=True,
                options=["resume_race"],
            )

        while not self.finished:
            self.current_lap += 1
            fuel_event = self._run_green_lap()
            self._sort_field()
            self._record_position_history()

            if fuel_event:
                return fuel_event

            if self.current_lap >= self.race.laps:
                self.finished = True
                return self._finish_event()

            incident = self._maybe_incident()
            if incident:
                return incident

            if self.current_lap in (self.race.stage_1_end, self.race.stage_2_end):
                return self._stage_end_event()

            if self._is_pit_window():
                return self._pit_window_event()

            if self.current_lap % 4 == 0:
                return self._race_control_event()

        return self._finish_event()

    def apply_decision(self, decision: str, **kwargs) -> RaceEvent:
        decision = decision.lower().strip()

        if decision == "continue":
            self.flag = "GREEN"
            return self._event("RACE_CONTROL", "Race continued", "Race control has allowed the race to continue.")

        if decision == "throw_caution":
            self.flag = "CAUTION"
            return self._event(
                "CAUTION",
                "Manual caution",
                "Race control has thrown the caution flag.",
                requires_decision=True,
                options=["open_pit_road", "restart", "red_flag"],
            )

        if decision == "open_pit_road":
            self.pit_road_open = True
            return self._event(
                "PIT_WINDOW",
                "Pit road open",
                "Pit road is open. Pitting under caution has limited track-position loss; pitting under green is costly.",
                requires_decision=True,
                options=["pit_leaders", "pit_all", "close_pit_road", "restart"],
            )

        if decision == "close_pit_road":
            self.pit_road_open = False
            return self._event("RACE_CONTROL", "Pit road closed", "Pit road is now closed.")

        if decision == "pit_all":
            self._pit_stop(self.running_order())
            self.pit_road_open = False
            self._sort_field()
            return self._event(
                "PIT_WINDOW",
                "Pit stops complete",
                "All running cars pitted. Fresh tires/fuel were added, and the field was reordered by pit crew performance.",
            )

        if decision == "pit_leaders":
            leaders = self.running_order()[:8]
            self._pit_stop(leaders)
            self.pit_road_open = False
            self._sort_field()
            return self._event(
                "PIT_WINDOW",
                "Leaders pit",
                "The top 8 cars pitted. Stay-out cars kept track position, and pit crews decided the race off pit road.",
            )

        if decision == "restart":
            self.flag = "GREEN"
            self.pit_road_open = False
            self.restart_intensity = max(self.restart_intensity, 2.5)
            return self._event("GREEN_FLAG", "Restart", f"The race restarts on lap {self.current_lap + 1}.")

        if decision == "red_flag":
            self.flag = "RED"
            return self._event(
                "RACE_CONTROL",
                "Red flag",
                "The race has been temporarily stopped.",
                requires_decision=True,
                options=["resume_race", "open_pit_road"],
            )

        if decision == "resume_race":
            self.flag = "CAUTION"
            return self._event(
                "RACE_CONTROL",
                "Red flag lifted",
                "Cars are rolling again under caution.",
                requires_decision=True,
                options=["open_pit_road", "restart"],
            )

        if decision == "apply_penalty":
            driver_id = kwargs.get("driver_id")
            penalty = int(kwargs.get("penalty", 5))
            for car in self.cars:
                if car.driver.driver_id == driver_id:
                    car.score -= penalty
                    car.penalties += 1
                    self._sort_field()
                    return self._event(
                        "RACE_CONTROL",
                        "Penalty applied",
                        f"{car.driver.name} was penalized {penalty} points of track position.",
                    )
            return self._event("RACE_CONTROL", "Penalty failed", f"No driver found for ID {driver_id}.")

        if decision == "warn_aggressive_drivers":
            self.field_aggression_modifier -= 5.0
            self.caution_modifier -= 0.05
            self.race_control_strictness += 1.0
            return self._event(
                "RACE_CONTROL",
                "Drivers warned",
                "Race control warned aggressive drivers. Incident risk has been meaningfully reduced.",
            )

        if decision == "increase_restart_intensity":
            self.restart_intensity += 3.0
            self.caution_modifier += 0.05
            return self._event(
                "RACE_CONTROL",
                "Restart intensity increased",
                "Race control will allow harder racing. Restart intensity and incident risk have increased.",
            )

        if decision == "calm_field_down":
            self.field_aggression_modifier -= 7.0
            self.caution_modifier -= 0.07
            self.restart_intensity = max(0.0, self.restart_intensity - 1.5)
            return self._event(
                "RACE_CONTROL",
                "Field calmed down",
                "Race control has calmed the field. Aggression and caution risk were reduced.",
            )

        return self._event(
            "RACE_CONTROL",
            "Unknown decision",
            f"Decision '{decision}' was not recognized.",
            requires_decision=True,
            options=["continue"],
        )

    def pit_cars(self, selected_cars: list[RunningCar]) -> RaceEvent:
        if not selected_cars:
            return self._event(
                "PIT_WINDOW",
                "No cars selected",
                "No cars were selected for pit service.",
            )

        self._pit_stop(selected_cars)
        self._sort_field()

        names = ", ".join([car.driver.name for car in selected_cars[:5]])
        if len(selected_cars) > 5:
            names += "..."

        mode = "caution" if self.flag == "CAUTION" else "green-flag"

        return self._event(
            "PIT_WINDOW",
            "Manual pit stop",
            f"Pitted cars under {mode} conditions: {names}",
        )

    def retire_cars(self, selected_cars: list[RunningCar], reason: str = "Retired by race control") -> RaceEvent:
        if not selected_cars:
            return self._event(
                "RACE_CONTROL",
                "No cars selected",
                "No cars were selected to retire.",
            )

        names = []

        for car in selected_cars:
            car.damage_status = "OUT"
            car.crashed_out = True
            car.score -= 1000
            names.append(car.driver.name)

        self._sort_field()

        return self._event(
            "RACE_CONTROL",
            "Car retired",
            reason + ": " + ", ".join(names),
            requires_decision=False,
            data={"retired": names},
        )

    # ------------------------------------------------------------------
    # Public data
    # ------------------------------------------------------------------

    def running_order(self) -> list[RunningCar]:
        return sorted([car for car in self.cars if not car.crashed_out], key=lambda car: car.position)

    def standings_snapshot(self) -> list[dict]:
        rows = []
        for car in sorted(self.cars, key=lambda c: c.position):
            self._ensure_car_state(car)
            old_pos = self.last_positions.get(car.driver.driver_id, car.position)
            change = old_pos - car.position

            rows.append(
                {
                    "Pos": car.position,
                    "+/-": change,
                    "Car": car.driver.car_number,
                    "Driver": car.driver.name,
                    "Team": car.driver.team,
                    "Manufacturer": car.driver.manufacturer,
                    "Score": round(car.score, 2),
                    "Stage Pts": car.stage_points,
                    "Laps Led": car.laps_led,
                    "Pits": car.pit_stops,
                    "Last Pit +/-": car.last_pit_delta,
                    "Tire Age": car.tire_age,
                    "Fuel": car.fuel,
                    "Penalties": car.penalties,
                    "Status": car.damage_status,
                }
            )

        return rows

    def final_results(self) -> list[dict]:
        rows = []
        for car in sorted(self.cars, key=lambda c: c.position):
            self._ensure_car_state(car)
            finish = car.position
            race_points = BASE_POINTS.get(finish, 1)

            bonus = car.bonus_points
            if finish == 1:
                bonus += 5
            if car.laps_led > 0:
                bonus += 1

            rows.append(
                {
                    "Finish": finish,
                    "Driver ID": car.driver.driver_id,
                    "Driver": car.driver.name,
                    "Team": car.driver.team,
                    "Manufacturer": car.driver.manufacturer,
                    "Race Points": race_points,
                    "Stage Points": car.stage_points,
                    "Bonus Points": bonus,
                    "Total Points": race_points + car.stage_points + bonus,
                    "Laps Led": car.laps_led,
                    "Pit Stops": car.pit_stops,
                    "Penalties": car.penalties,
                    "Status": car.damage_status,
                }
            )

        return rows

    # ------------------------------------------------------------------
    # Lap simulation
    # ------------------------------------------------------------------

    def _run_green_lap(self) -> RaceEvent | None:
        fuel_failures = []

        for car in self.running_order():
            car.score += self._lap_score(car)

            if car.fuel <= 0 and not car.crashed_out:
                car.damage_status = "OUT"
                car.crashed_out = True
                car.score -= 1000
                fuel_failures.append(car.driver.name)

        self._sort_field()

        if self.running_order():
            self.running_order()[0].laps_led += 1

        self.restart_intensity = max(0.0, self.restart_intensity - 0.5)

        if fuel_failures:
            self.flag = "CAUTION"
            return self._event(
                "MECHANICAL",
                "Out of fuel",
                "Out of fuel: " + ", ".join(fuel_failures),
                requires_decision=True,
                options=["open_pit_road", "red_flag", "restart"],
                data={"out_of_fuel": fuel_failures},
            )

        return None

    def _lap_score(self, car: RunningCar) -> float:
        self._ensure_car_state(car)

        if car.crashed_out or car.damage_status == "OUT":
            return -1000

        driver = car.driver

        car.tire_age += 1
        car.fuel = max(0, car.fuel - 4)

        base = self._driver_track_rating(driver) / 10
        consistency_bonus = (driver.consistency - 50) / 14
        tire_saving_bonus = ((driver.tire_saving - 50) / 18) * (
            self.current_lap / max(self.race.laps, 1)
        )

        fresh_tire_bonus = car.tire_bonus
        if car.tire_bonus > 0:
            car.tire_bonus = max(0, car.tire_bonus - 0.75)

        tire_wear_penalty = 0
        if car.tire_age >= 10:
            tire_wear_penalty += 4
        if car.tire_age >= 15:
            tire_wear_penalty += 8
        if car.tire_age >= 20:
            tire_wear_penalty += 15
        if car.tire_age >= 25:
            tire_wear_penalty += 30

        fuel_penalty = 0
        if car.fuel <= 15:
            fuel_penalty = 8
        if car.fuel <= 10:
            fuel_penalty = 15
        if car.fuel <= 5:
            fuel_penalty = 30
        if car.fuel <= 0:
            fuel_penalty = 100

        damage_multiplier = 1.0
        damage_penalty = 0

        if car.damage_status == "DAMAGED":
            damage_multiplier = 0.70
            damage_penalty = 5
        elif car.damage_status == "HEAVY_DAMAGE":
            damage_multiplier = 0.40
            damage_penalty = 14
        elif car.damage_status == "OUT":
            return -1000

        chaos_noise = self.random.gauss(0, self.race.chaos / 1.8)

        aggression_effect = (driver.aggression + self.field_aggression_modifier - 50) / 30
        if self.restart_intensity > 0:
            aggression_effect += self.restart_intensity * 0.45

        mistake_chance = max(0, 72 - driver.consistency) / 500
        if self.random.random() < mistake_chance:
            chaos_noise -= self.random.randint(3, 10)

        return (
            (base * damage_multiplier)
            + consistency_bonus
            + tire_saving_bonus
            + fresh_tire_bonus
            + aggression_effect
            + chaos_noise
            - tire_wear_penalty
            - fuel_penalty
            - damage_penalty
        )

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------

    def _maybe_incident(self) -> RaceEvent | None:
        if self.flag == "CAUTION":
            return None

        running = self.running_order()
        if not running:
            return None

        field_aggression = sum(car.driver.aggression for car in running) / max(1, len(running))

        chance = (
            0.01
            + (self.race.chaos * 0.01)
            + ((field_aggression - 50) / 1200)
            + self.caution_modifier
            + (self.restart_intensity * 0.015)
        )

        chance = max(0.005, min(0.35, chance))

        if self.random.random() > chance:
            return None

        incident_types = [
            "single_car_spin",
            "multi_car_crash",
            "tire_failure",
            "mechanical",
            "debris",
            "aggressive_contact",
        ]

        weights = [22, 24, 14, 10, 18, max(5, self.race.chaos * 3)]
        incident_type = self.random.choices(incident_types, weights=weights, k=1)[0]
        return self._create_incident_event(incident_type)

    def _create_incident_event(self, incident_type: str) -> RaceEvent | None:
        running = self.running_order()
        if not running:
            return None

        severity = self.random.choices(["minor", "moderate", "major"], weights=[50, 35, 15], k=1)[0]
        if self.race.track_type == "superspeedway":
            severity = self.random.choices(["minor", "moderate", "major"], weights=[30, 40, 30], k=1)[0]

        involved: list[RunningCar] = []

        if incident_type == "debris":
            message = self.random.choice(INCIDENT_TEMPLATES[incident_type])
        else:
            count = 1
            if incident_type in ("multi_car_crash", "aggressive_contact"):
                max_count = 6 if severity == "major" else 4
                count = min(len(running), self.random.randint(2, max_count))

            involved = sorted(
                running,
                key=lambda car: (
                    self.random.random()
                    + ((100 - car.driver.consistency) / 100)
                    + ((car.driver.aggression + self.field_aggression_modifier) / 230)
                ),
                reverse=True,
            )[:count]

            names = [car.driver.name for car in involved]
            a = names[0] if len(names) > 0 else "A driver"
            b = names[1] if len(names) > 1 else "another car"
            c = names[2] if len(names) > 2 else "traffic"

            message = self.random.choice(INCIDENT_TEMPLATES[incident_type]).format(a=a, b=b, c=c)

        out, damaged, heavy = [], [], []

        for car in involved:
            self._ensure_car_state(car)
            car.cautions_involved += 1

            dnf_chance = {"minor": 0.03, "moderate": 0.15, "major": 0.38}[severity]
            heavy_chance = {"minor": 0.10, "moderate": 0.35, "major": 0.55}[severity]

            if incident_type in ("mechanical", "tire_failure"):
                dnf_chance += 0.15

            roll = self.random.random()

            if roll < dnf_chance:
                car.crashed_out = True
                car.damage_status = "OUT"
                car.score -= 1000
                out.append(car.driver.name)
            elif roll < dnf_chance + heavy_chance:
                car.damage_status = "HEAVY_DAMAGE"
                car.score -= self.random.randint(25, 55)
                heavy.append(car.driver.name)
            else:
                car.damage_status = "DAMAGED"
                car.score -= self.random.randint(8, 25)
                damaged.append(car.driver.name)

        self.flag = "CAUTION"
        self._sort_field()

        details = []
        if out:
            details.append("OUT: " + ", ".join(out))
        if heavy:
            details.append("HEAVY DAMAGE: " + ", ".join(heavy))
        if damaged:
            details.append("DAMAGED: " + ", ".join(damaged))

        full_message = message + ("\n\n" + "\n".join(details) if details else "")

        return self._event(
            "CRASH" if involved else "CAUTION",
            f"{incident_type.replace('_', ' ').title()} — {severity.title()}",
            full_message,
            requires_decision=True,
            options=["open_pit_road", "red_flag", "restart"],
            data={
                "incident_type": incident_type,
                "severity": severity,
                "out": out,
                "damaged": damaged,
                "heavy_damage": heavy,
            },
        )

    # ------------------------------------------------------------------
    # Stages / race control / finish
    # ------------------------------------------------------------------

    def _stage_end_event(self) -> RaceEvent:
        ordered = self.running_order()
        for pos, car in enumerate(ordered[:10], start=1):
            car.stage_points += STAGE_POINTS[pos]

        self.flag = "CAUTION"
        stage_winner = ordered[0].driver.name if ordered else "No running cars"

        return self._event(
            "STAGE_END",
            f"Stage ends on lap {self.current_lap}",
            f"Stage winner: {stage_winner}. Stage points have been awarded.",
            requires_decision=True,
            options=["open_pit_road", "restart"],
            data={"stage_winner": stage_winner},
        )

    def _pit_window_event(self) -> RaceEvent:
        return self._event(
            "PIT_WINDOW",
            "Pit window",
            f"Scheduled pit window reached on lap {self.current_lap}. Pitting under green costs major track position but gives fresh tires and fuel.",
            requires_decision=True,
            options=["pit_all", "pit_leaders", "continue"],
        )

    def _race_control_event(self) -> RaceEvent:
        return self._event(
            "RACE_CONTROL",
            "Race control review",
            f"Race control review at lap {self.current_lap}.",
            requires_decision=True,
            options=[
                "continue",
                "warn_aggressive_drivers",
                "calm_field_down",
                "increase_restart_intensity",
                "throw_caution",
                "open_pit_road",
                "apply_penalty",
            ],
        )

    def _finish_event(self) -> RaceEvent:
        self._sort_field()
        winner = self.running_order()[0].driver.name if self.running_order() else "No running cars"

        return self._event(
            "RACE_FINISH",
            "Checkered flag",
            f"{winner} wins the {self.race.name}.",
            requires_decision=False,
            data={"winner": winner, "results": self.final_results()},
        )

    # ------------------------------------------------------------------
    # Pit logic
    # ------------------------------------------------------------------

    def _pit_stop(self, cars: list[RunningCar]) -> None:
        if self.flag == "CAUTION":
            self._caution_pit_stop(cars)
        else:
            self._green_flag_pit_stop(cars)

    def _green_flag_pit_stop(self, cars: list[RunningCar]) -> None:
        for car in cars:
            self._ensure_car_state(car)

            pit_crew_gain = (car.driver.pit_crew - 50) / 3
            pit_variance = self.random.gauss(0, 6)
            track_position_loss = self.random.uniform(25, 45)

            damage_pit_delay = 0
            if car.damage_status == "DAMAGED":
                damage_pit_delay = self.random.uniform(8, 16)
            elif car.damage_status == "HEAVY_DAMAGE":
                damage_pit_delay = self.random.uniform(18, 35)

            car.tire_age = 0
            car.fuel = 100
            car.tire_bonus = self.random.uniform(12, 20)

            car.score -= track_position_loss + damage_pit_delay
            car.score += pit_crew_gain + pit_variance
            car.pit_stops += 1
            car.last_pit_delta = round(pit_crew_gain + pit_variance - track_position_loss - damage_pit_delay, 2)

        self._sort_field()

    def _caution_pit_stop(self, cars: list[RunningCar]) -> None:
        pre_pit_order = list(self.running_order())

        pit_group = [car for car in pre_pit_order if car in cars]
        stay_out_group = [car for car in pre_pit_order if car not in cars]

        pit_results: list[tuple[float, RunningCar]] = []

        for car in pit_group:
            self._ensure_car_state(car)

            old_pos = car.position

            damage_pit_penalty = 0
            if car.damage_status == "DAMAGED":
                damage_pit_penalty = self.random.uniform(8, 16)
            elif car.damage_status == "HEAVY_DAMAGE":
                damage_pit_penalty = self.random.uniform(18, 35)

            pit_crew_score = (
                car.driver.pit_crew * 0.70
                + car.driver.consistency * 0.15
                + self.random.gauss(0, 8)
                - damage_pit_penalty
            )

            pit_results.append((pit_crew_score, car))

            car.tire_age = 0
            car.fuel = 100
            car.tire_bonus = self.random.uniform(12, 20)
            car.pit_stops += 1
            car._old_pit_position = old_pos

        pit_results.sort(reverse=True, key=lambda item: item[0])
        pit_exit_order = [car for _, car in pit_results]

        new_order = stay_out_group + pit_exit_order

        for pos, car in enumerate(new_order, start=1):
            old_pos = getattr(car, "_old_pit_position", car.position)
            car.position = pos
            car.score = 1000 - (pos * 12)
            car.last_pit_delta = old_pos - pos

            if hasattr(car, "_old_pit_position"):
                delattr(car, "_old_pit_position")

        self._sort_field()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_pit_window(self) -> bool:
        if self.current_lap <= self.race.stage_1_end:
            return False
        if self.current_lap >= self.race.laps - 1:
            return False
        return self.current_lap % 5 == 0

    def _qualify(self, drivers: list[Driver]) -> dict[str, int]:
        raw = []
        for driver in drivers:
            score = (
                driver.qualifying * 0.50
                + driver.speed * 0.20
                + driver.consistency * 0.10
                + self.random.gauss(0, 14)
            )
            raw.append((score, driver))

        raw.sort(reverse=True, key=lambda item: item[0])
        return {
            driver.driver_id: pos
            for pos, (_, driver) in enumerate(raw, start=1)
        }

    def _driver_track_rating(self, driver: Driver) -> float:
        weights = TRACK_WEIGHTS.get(self.race.track_type, TRACK_WEIGHTS["speedway"])

        return (
            driver.speed * weights["speed"]
            + driver.consistency * weights["consistency"]
            + driver.aggression * weights["aggression"]
            + driver.tire_saving * weights["tire_saving"]
            + driver.pit_crew * weights["pit_crew"]
        )

    def _build_cars_from_grid(self, grid: dict[str, int]) -> None:
        self.cars = []

        for driver in self.drivers:
            qpos = grid.get(driver.driver_id, len(self.drivers))
            starting_score = self._driver_track_rating(driver) + max(0, len(self.drivers) - qpos) * 0.35

            car = RunningCar(
                driver=driver,
                position=qpos,
                qualifying_position=qpos,
                score=starting_score,
            )

            self._ensure_car_state(car)
            self.cars.append(car)

        self._sort_field(initial=True)

    def _sort_field(self, initial: bool = False) -> None:
        if not initial:
            self.last_positions = {
                car.driver.driver_id: car.position
                for car in self.cars
            }
        else:
            self.last_positions = {}

        running = sorted(
            [car for car in self.cars if not car.crashed_out],
            key=lambda car: car.score,
            reverse=True,
        )

        out = sorted(
            [car for car in self.cars if car.crashed_out],
            key=lambda car: car.score,
            reverse=True,
        )

        for pos, car in enumerate(running + out, start=1):
            car.position = pos

    def _record_position_history(self) -> None:
        self.position_history.append(
            {
                "lap": self.current_lap,
                "positions": {
                    car.driver.driver_id: car.position
                    for car in self.cars
                },
            }
        )

    def _ensure_car_state(self, car: RunningCar) -> None:
        defaults = {
            "damage_status": "RUNNING",
            "tire_age": 0,
            "fuel": 100,
            "tire_bonus": 0.0,
            "last_pit_delta": 0,
        }

        for attr, default in defaults.items():
            if not hasattr(car, attr):
                setattr(car, attr, default)

    def _event(
        self,
        event_type: str,
        title: str,
        message: str,
        requires_decision: bool = False,
        options: list[str] | None = None,
        data: dict | None = None,
    ) -> RaceEvent:
        event = RaceEvent(
            event_type=event_type,
            lap=self.current_lap,
            title=title,
            message=message,
            requires_decision=requires_decision,
            options=options or [],
            data=data or {},
        )

        self.event_log.append(event)
        return event
