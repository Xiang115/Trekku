/** Mirrors backend/models.py. Source of truth: the FastAPI schemas. */

export type EntityType = "hotels" | "attractions" | "flights";

export interface TripParams {
  origin_state: string | null;
  city: string | null;
  budget: number | null;
  days: number | null;
  travel_date: string | null;
  travelers: number;
}

/** price_per_night may be a scalar (chat shape) or an object (full Hotel). */
export type PricePerNight = number | { min: number; max: number; currency: string };

export interface ItineraryHotel {
  hotel_id: string;
  name: string;
  price_per_night: PricePerNight;
}

export interface ItineraryAttraction {
  attraction_id: string;
  name: string;
  estimated_duration: string | null;
}

export interface ItineraryDay {
  day: number;
  hotel: ItineraryHotel | null;
  attractions: ItineraryAttraction[];
  notes: string;
}

export interface ItineraryFlight {
  flight_id: string;
  airline: string;
  flight_number: string;
  price: number;
}

/** Flattened itinerary returned inline by POST /agent/chat. */
export interface ChatItinerary {
  days: ItineraryDay[];
  flight: ItineraryFlight | null;
  /** AI-estimated whole-trip costs with no deterministic knowledge-base price. */
  estimated_meals_cost: number;
  estimated_transport_cost: number;
  total_estimated_cost: number;
}

export interface ChatRequest {
  session_id?: string | null;
  message: string;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  itinerary_id: string | null;
  params_collected: TripParams;
  itinerary: ChatItinerary | null;
}

export interface ConversationTurn {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface AgentSession {
  session_id: string;
  created_at: string;
  updated_at: string;
  trip_params: TripParams;
  conversation: ConversationTurn[];
  last_itinerary_id: string | null;
  status: "active" | "completed";
}

/** GET /agent/itinerary/{id} — same data nested under `content`. */
export interface GeneratedItinerary {
  itinerary_id: string;
  session_id: string;
  created_at: string;
  city: string;
  days: number;
  budget: number;
  travel_date: string | null;
  content: ChatItinerary;
}

export interface FeedbackRequest {
  itinerary_id: string;
  entity_id?: string | null;
  entity_type?: EntityType | null;
  rating?: number | null;
  comment?: string | null;
  signal?: number;
}

export interface FeedbackResponse {
  feedback_id: string;
}

export interface ModifyRequest {
  itinerary_id: string;
  original_entity_id: string;
  replacement_entity_id: string;
  entity_type: EntityType;
}

export interface ModifyResponse {
  feedback_ids: string[];
}

export interface EntitySummary {
  entity_id: string;
  name: string;
  city: string;
  /** Hotel nightly midpoint or flight fare; null for attractions. */
  price: number | null;
}

export interface TrendPoint {
  date: string;
  rating: number | null;
  review_count: number | null;
  price_min: number | null;
}

export interface TrendResponse {
  entity_id: string;
  entity_type: string;
  name: string;
  city: string;
  from_date: string | null;
  to_date: string | null;
  data: TrendPoint[];
}
