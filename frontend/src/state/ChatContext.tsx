import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import * as api from "../api/client";
import { ApiError, type ProgressEvent } from "../api/client";
import { recomputeTotal } from "../lib/cost";
import type {
  ChatItinerary,
  ConversationTurn,
  EntityType,
  TripParams,
} from "../api/types";

type ChatStatus = "idle" | "sending" | "hydrating";

interface ChatContextValue {
  sessionId: string | null;
  conversation: ConversationTurn[];
  paramsCollected: TripParams | null;
  currentItinerary: ChatItinerary | null;
  itineraryId: string | null;
  status: ChatStatus;
  progress: ProgressEvent | null;
  error: string | null;
  send: (message: string) => Promise<void>;
  resetSession: () => void;
  applyLocalSwap: (
    entityType: EntityType,
    originalId: string,
    replacement: { entity_id: string; name: string; price?: number | null },
  ) => void;
}

const SESSION_KEY = "trekkuSessionId";
const now = () => new Date().toISOString();

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(() =>
    localStorage.getItem(SESSION_KEY),
  );
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [paramsCollected, setParamsCollected] = useState<TripParams | null>(null);
  const [currentItinerary, setCurrentItinerary] = useState<ChatItinerary | null>(null);
  const [itineraryId, setItineraryId] = useState<string | null>(null);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const persistSession = useCallback((id: string) => {
    setSessionId(id);
    localStorage.setItem(SESSION_KEY, id);
  }, []);

  const resetSession = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    setSessionId(null);
    setConversation([]);
    setParamsCollected(null);
    setCurrentItinerary(null);
    setItineraryId(null);
    setError(null);
    setStatus("idle");
    setProgress(null);
  }, []);

  // Rehydrate an existing session (conversation + last itinerary) on first load.
  const hydratedRef = useRef(false);
  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    const existing = localStorage.getItem(SESSION_KEY);
    if (!existing) return;

    let cancelled = false;
    (async () => {
      setStatus("hydrating");
      try {
        const session = await api.getSession(existing);
        if (cancelled) return;
        setConversation(session.conversation ?? []);
        setParamsCollected(session.trip_params ?? null);
        if (session.last_itinerary_id) {
          setItineraryId(session.last_itinerary_id);
          try {
            const itin = await api.getItinerary(session.last_itinerary_id);
            if (!cancelled) setCurrentItinerary(itin.content);
          } catch {
            /* itinerary fetch is best-effort on reload */
          }
        }
      } catch (err) {
        if (cancelled) return;
        // Stale/unknown session — start fresh.
        if (err instanceof ApiError && err.status === 404) {
          localStorage.removeItem(SESSION_KEY);
          setSessionId(null);
        }
      } finally {
        if (!cancelled) setStatus("idle");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const send = useCallback(
    async (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || status === "sending") return;

      setError(null);
      setStatus("sending");
      setProgress(null);
      setConversation((prev) => [...prev, { role: "user", content: trimmed, timestamp: now() }]);

      try {
        await api.chatStream(
          { session_id: sessionId, message: trimmed },
          {
            onStatus: (event) => setProgress(event),
            onResult: (res) => {
              persistSession(res.session_id);
              setConversation((prev) => [
                ...prev,
                { role: "assistant", content: res.reply, timestamp: now() },
              ]);
              setParamsCollected(res.params_collected);
              if (res.itinerary_id) setItineraryId(res.itinerary_id);
              if (res.itinerary) setCurrentItinerary(res.itinerary);
            },
            onError: (err) => setError(err.message),
          },
        );
      } catch (err) {
        const msg =
          err instanceof ApiError ? err.message : "Something went wrong sending your message.";
        setError(msg);
      } finally {
        setStatus("idle");
        setProgress(null);
      }
    },
    [sessionId, status, persistSession],
  );

  const applyLocalSwap = useCallback<ChatContextValue["applyLocalSwap"]>(
    (entityType, originalId, replacement) => {
      setCurrentItinerary((prev) => {
        if (!prev) return prev;
        const days = prev.days.map((day) => {
          if (entityType === "hotels" && day.hotel?.hotel_id === originalId) {
            return {
              ...day,
              hotel: {
                ...day.hotel,
                hotel_id: replacement.entity_id,
                name: replacement.name,
                // Carry the new nightly rate when one is known; otherwise keep the old.
                price_per_night:
                  replacement.price ?? day.hotel.price_per_night,
              },
            };
          }
          if (entityType === "attractions") {
            return {
              ...day,
              attractions: day.attractions.map((a) =>
                a.attraction_id === originalId
                  ? { ...a, attraction_id: replacement.entity_id, name: replacement.name }
                  : a,
              ),
            };
          }
          return day;
        });
        let flight = prev.flight;
        if (entityType === "flights" && flight?.flight_id === originalId) {
          flight = {
            ...flight,
            flight_id: replacement.entity_id,
            airline: replacement.name,
            price: replacement.price ?? flight.price,
          };
        }
        // Recompute the deterministic total so the badge and breakdown stay in sync.
        const total = recomputeTotal({ ...prev, days, flight }, paramsCollected?.travelers ?? 1);
        return { ...prev, days, flight, total_estimated_cost: total };
      });
    },
    [paramsCollected],
  );

  const value = useMemo<ChatContextValue>(
    () => ({
      sessionId,
      conversation,
      paramsCollected,
      currentItinerary,
      itineraryId,
      status,
      progress,
      error,
      send,
      resetSession,
      applyLocalSwap,
    }),
    [
      sessionId,
      conversation,
      paramsCollected,
      currentItinerary,
      itineraryId,
      status,
      progress,
      error,
      send,
      resetSession,
      applyLocalSwap,
    ],
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within a ChatProvider");
  return ctx;
}
