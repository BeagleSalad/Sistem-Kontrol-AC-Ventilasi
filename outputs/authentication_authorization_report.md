# Authentication and Authorization Report

## Indoor Air Quality Monitor

### Overview

The Indoor Air Quality Monitor is a simulated IoT web application for university classrooms. A virtual sensor submits temperature, humidity, CO2, PM2.5, and occupancy readings to a FastAPI backend. Authorized classroom users view readings and control their classroom's virtual air conditioner through a React dashboard. PostgreSQL stores the system data and security-related records.

This report explains how the application addresses four core authentication and authorization components.

## 1. Authenticated entities

The system recognises three main entities:

| Entity | Purpose | Example |
| --- | --- | --- |
| User | A person or a classroom PC operator using the web dashboard | `room-a101-operator` |
| Administrator | A campus-level user who manages all classrooms | `campus-admin` |
| Device | An IoT sensor identity that submits readings | `iaq-a101-01` |

Rooms are stored as protected resources, rather than as authenticated entities. A user and a device are each assigned to a room. For example, the Room A-101 operator and the `iaq-a101-01` sensor are both associated with Room A-101.

## 2. Authentication approach

Human users authenticate with a username and password through the dashboard login page. Passwords are not stored directly. Instead, PostgreSQL stores an Argon2 password hash, created by the `pwdlib` library. When a user logs in, FastAPI verifies the supplied password against its stored hash.

On successful login, the backend creates a signed JSON Web Token (JWT). The React dashboard stores that token in browser session storage and includes it as a `Bearer` token in later API requests. The token expires after eight hours.

Devices use a separate mechanism. The simulator identifies itself with a device ID and API key through `X-Device-ID` and `X-API-Key` HTTP headers. Like passwords, API keys are stored as hashes, so the raw device secret is not retained in the database. This prevents a classroom device from impersonating a human dashboard user.

The classroom PC's campus Ethernet connection is useful as a deployment assumption, because the room-operator account can be used only on that trusted PC. However, the network connection is not used as the primary credential; an IP address alone would be weak because it may change or be spoofed.

## 3. Roles

The initial system has two human roles and one device identity type:

| Role or type | Permissions |
| --- | --- |
| `room_operator` | View readings, alerts, and AC state for its assigned classroom; change AC state for that classroom only. |
| `admin` | View and control all classrooms. This role is intended to add rooms, classroom accounts, and sensor devices in a future administration page. |
| Device | Submit readings only for the room registered to that device; retrieve that room's AC state for the simulation. |

This design allows the classroom PC to operate its own room without giving it campus-wide control. It also separates physical/simulated device actions from human actions.

## 4. Authorization implementation

Authorization is performed by the FastAPI backend after authentication. The frontend never accesses PostgreSQL directly and cannot make authorization decisions on its own.

For user requests, the backend reads the JWT, loads the active user from PostgreSQL, and checks the user role and assigned room. An administrator is permitted to access every room. A room operator is permitted only when the requested room ID matches the `assigned_room_id` stored for that user.

For example, before processing an AC request such as `PUT /api/rooms/Room A-101/ac`, the backend:

1. Validates the JWT.
2. Finds the user record in PostgreSQL.
3. Finds the requested room.
4. Allows the request if the user is an administrator, or if the room is assigned to that room operator.
5. Returns `403 Forbidden` if the user attempts to control another classroom.

For sensor-reading requests, the backend validates the device ID and API key. It obtains the device's registered room from PostgreSQL, then writes the reading using that room association. The simulator cannot choose a different room simply by changing the request body.

## Database support

PostgreSQL stores the relationships used by authorization:

```text
users.assigned_room_id  -> rooms.id
devices.room_id         -> rooms.id
readings.device_id      -> devices.id
readings.room_id        -> rooms.id
control_commands.issued_by_user_id -> users.id
```

The `control_commands` table records which user issued an AC change. This supports accountability and provides an audit trail for a future campus deployment.

## Conclusion

The application addresses authentication by using hashed passwords for human users, hashed API keys for devices, and JWTs for authenticated browser sessions. It addresses authorization through role-based access control and room assignments stored in PostgreSQL. As a result, a classroom PC can control only its own classroom while an administrator can supervise the complete campus system.
