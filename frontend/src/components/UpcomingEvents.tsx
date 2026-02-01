import { Calendar } from "lucide-react";
import type { Event } from "../types";

interface UpcomingEventsProps {
  events: Event[];
}

function formatDate(date: Date): string {
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function getDaysUntil(date: Date): number {
  const now = new Date();
  return Math.floor((date.getTime() - now.getTime()) / (24 * 60 * 60 * 1000));
}

export function UpcomingEvents({ events }: UpcomingEventsProps) {
  const displayEvents = events.slice(0, 5);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">다가오는 행사</span>
        <Calendar size={18} color="#6b7280" />
      </div>
      <div className="list">
        {displayEvents.length === 0 ? (
          <div className="empty">예정된 행사가 없습니다</div>
        ) : (
          displayEvents.map((event) => (
            <div key={event.id} className="list-item">
              <div>
                <div className="list-item-title">{event.title}</div>
                <div className="list-item-sub">
                  {event.location} | {event.manager}
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="badge blue">{formatDate(event.startDate)}</div>
                <div
                  className="list-item-sub"
                  style={{ marginTop: 4, textAlign: "right" }}
                >
                  {getDaysUntil(event.startDate)}일 후
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
