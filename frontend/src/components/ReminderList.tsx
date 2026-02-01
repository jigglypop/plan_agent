import { Bell } from "lucide-react";
import type { Reminder } from "../types";

interface ReminderListProps {
  reminders: Reminder[];
}

export function ReminderList({ reminders }: ReminderListProps) {
  const displayReminders = reminders.slice(0, 5);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">리마인더</span>
        <Bell size={18} color="#6b7280" />
      </div>
      <div className="list">
        {displayReminders.length === 0 ? (
          <div className="empty">예정된 알림이 없습니다</div>
        ) : (
          displayReminders.map((reminder) => (
            <div key={reminder.eventId} className="list-item">
              <div>
                <div className="list-item-title">{reminder.eventTitle}</div>
                <div className="list-item-sub">{reminder.message}</div>
              </div>
              <span className={`badge ${reminder.priority}`}>
                D-{reminder.daysUntil}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
