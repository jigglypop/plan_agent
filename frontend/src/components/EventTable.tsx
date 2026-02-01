import type { Event } from "../types";

interface EventTableProps {
  events: Event[];
}

function formatDate(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("ko-KR").format(amount) + "원";
}

export function EventTable({ events }: EventTableProps) {
  const displayEvents = events.slice(0, 10);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">최근 행사 목록</span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="table">
          <thead>
            <tr>
              <th>행사명</th>
              <th>카테고리</th>
              <th>일자</th>
              <th>장소</th>
              <th>담당자</th>
              <th>참석</th>
              <th>예산</th>
              <th>상태</th>
            </tr>
          </thead>
          <tbody>
            {displayEvents.map((event) => (
              <tr key={event.id}>
                <td style={{ fontWeight: 500 }}>{event.title}</td>
                <td>{event.category}</td>
                <td>{formatDate(event.startDate)}</td>
                <td>{event.location}</td>
                <td>{event.manager}</td>
                <td>
                  {event.actualAttendees > 0
                    ? `${event.actualAttendees}/${event.expectedAttendees}`
                    : event.expectedAttendees}
                </td>
                <td>{formatCurrency(event.budget)}</td>
                <td>
                  <span className="status">
                    <span className={`status-dot ${event.status}`} />
                    {event.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
