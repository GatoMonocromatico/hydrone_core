# Estado do veiculo publicado pela ponte em /hydrone/mission_state.

std_msgs/Header header

string vehicle_id

bool connected
bool armed
string mode

float64 latitude
float64 longitude
float32 altitude

uint32 last_cmd_id       # ultimo cmd_id aceito (0 = nenhum ainda)
float64 target_latitude
float64 target_longitude
float32 target_altitude

bool waypoint_reached    # true quando dentro do raio de aceitacao do alvo
