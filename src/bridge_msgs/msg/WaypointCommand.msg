# Comando de waypoint publicado pelo planejador em /hydrone/waypoint_cmd.

std_msgs/Header header

uint32 cmd_id          # id de correlacao, ecoado em MissionState.last_cmd_id
string vehicle_id       # veiculo de destino (vazio = qualquer um)

float64 latitude
float64 longitude
float32 altitude
float32 hold_time_s     # tempo de permanencia sobre o waypoint (0 = so passar)
