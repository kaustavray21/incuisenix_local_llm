export function formatTimestamp(totalSeconds) {
    // Ensure we are working with a number
    const time = parseFloat(totalSeconds);
    if (isNaN(time)) return "00:00:00";

    // Calculate components
    const hours = Math.floor(time / 3600);
    const minutes = Math.floor((time % 3600) / 60);
    const seconds = Math.floor(time % 60); // Removes milliseconds

    // Pad with leading zeros
    const paddedHours = hours.toString().padStart(2, '0');
    const paddedMinutes = minutes.toString().padStart(2, '0');
    const paddedSeconds = seconds.toString().padStart(2, '0');

    return `${paddedHours}:${paddedMinutes}:${paddedSeconds}`;
}