/**
 * Client-side itinerary costing. Mirrors backend agent._calculate_total_cost so the
 * displayed badge, breakdown and checkout summary stay consistent after a local swap.
 *
 * Hotels, flight and attractions are deterministic line items; meals and transport are
 * the AI agent's whole-trip estimates carried on the itinerary.
 *
 * Flights and hotels are per-person / per-room bookables, so they scale with the party
 * size. Meals and transport are NOT scaled here: the agent already sizes those whole-trip
 * estimates for the full party. Keep this in lockstep with backend _calculate_total_cost.
 */
import type { ChatItinerary, PricePerNight } from "../api/types";

/** Representative nightly rate as a scalar (object ranges collapse to their midpoint). */
export function hotelNightly(price: PricePerNight): number {
  if (typeof price === "number") return price;
  return Math.round((price.min + price.max) / 2);
}

export interface CostBreakdown {
  hotels: number;
  flight: number;
  attractions: number;
  meals: number;
  transport: number;
  /** Amount actually charged at checkout: the bookable entities (hotels + flight + attractions). */
  bookedTotal: number;
  /** AI estimates shown for awareness but not booked/charged (meals + transport). */
  estimatesTotal: number;
  /** Grand estimate = bookedTotal + estimatesTotal. */
  total: number;
}

export function costBreakdown(itin: ChatItinerary, travelers = 1): CostBreakdown {
  const party = Math.max(Math.trunc(travelers) || 1, 1);
  let hotels = 0;
  let attractions = 0;
  for (const day of itin.days) {
    if (day.hotel) hotels += hotelNightly(day.hotel.price_per_night) * party;
    // Attractions carry no price today; sum defensively in case future data adds one.
    for (const a of day.attractions) {
      attractions += (a as { price?: number }).price ?? 0;
    }
  }
  const flight = (itin.flight?.price ?? 0) * party;
  const meals = itin.estimated_meals_cost ?? 0;
  const transport = itin.estimated_transport_cost ?? 0;
  // Bookable entities are charged; meals/transport are estimates carried alongside.
  const bookedTotal = hotels + flight + attractions;
  const estimatesTotal = meals + transport;
  const round = (n: number) => Math.round(n * 100) / 100;
  return {
    hotels,
    flight,
    attractions,
    meals,
    transport,
    bookedTotal: round(bookedTotal),
    estimatesTotal: round(estimatesTotal),
    total: round(bookedTotal + estimatesTotal),
  };
}

export const recomputeTotal = (itin: ChatItinerary, travelers = 1): number =>
  costBreakdown(itin, travelers).total;
