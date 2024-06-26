package main

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/go-chi/chi"
	"github.com/go-chi/chi/middleware"
	"github.com/joho/godotenv"
)

type InstanceTypes struct {
	Data map[string]InstanceTypeData `json:"data"`
}

type InstanceTypeData struct {
	RegionsWithCapacityAvailable []Region `json:"regions_with_capacity_available"`
}

type Region struct {
	Name string `json:"name"`
}

type LaunchPayload struct {
	RegionName       string   `json:"region_name"`
	InstanceTypeName string   `json:"instance_type_name"`
	SSHKeyNames      []string `json:"ssh_key_names"`
	Quantity         int      `json:"quantity"`
}

type HealthStatus struct {
	Status string      `json:"status"`
	Result interface{} `json:"result,omitempty"`
	Error  string      `json:"error,omitempty"`
}

var (
	apiKey           string
	instanceTypeName string
	sshKeyName       string
	checkInterval    int
	errorWait        int
	port             int
	baseUrl          = "https://cloud.lambdalabs.com/api/v1/"
	healthStatus     = HealthStatus{Status: "starting"}
)

func init() {
	if err := godotenv.Load(); err != nil {
		log.Println("No .env file found")
	}

	apiKey = os.Getenv("LAMBDA_API_KEY")
	instanceTypeName = os.Getenv("INSTANCE_TYPE_NAME")
	if instanceTypeName == "" {
		instanceTypeName = "gpu_1x_a6000"
	}

	sshKeyName = os.Getenv("SSH_KEY_NAME")
	checkInterval, _ = strconv.Atoi(os.Getenv("CHECK_INTERVAL_SECONDS"))
	if checkInterval == 0 {
		checkInterval = 30
	}

	errorWait, _ = strconv.Atoi(os.Getenv("ERROR_WAIT_SECONDS"))
	if errorWait == 0 {
		errorWait = 10
	}

	port, _ = strconv.Atoi(os.Getenv("PORT"))
	if port == 0 {
		port = 5000
	}
}

func getInstanceTypes() (InstanceTypes, error) {
	log.Printf("Checking availability for instance type %s...", instanceTypeName)
	client := &http.Client{}
	req, err := http.NewRequest("GET", baseUrl+"instance-types", nil)
	if err != nil {
		return InstanceTypes{}, err
	}

	req.SetBasicAuth(apiKey, "")
	resp, err := client.Do(req)
	if err != nil {
		return InstanceTypes{}, err
	}
	defer resp.Body.Close()

	var instanceTypes InstanceTypes
	err = json.NewDecoder(resp.Body).Decode(&instanceTypes)
	if err != nil {
		return InstanceTypes{}, err
	}

	return instanceTypes, nil
}

func checkInstanceAvailability(instanceTypes InstanceTypes) (string, error) {
	if data, exists := instanceTypes.Data[instanceTypeName]; exists {
		if len(data.RegionsWithCapacityAvailable) > 0 {
			return data.RegionsWithCapacityAvailable[0].Name, nil
		}
	}
	return "", nil
}

func launchInstance(regionName string) (interface{}, error) {
	client := &http.Client{}
	payload := LaunchPayload{
		RegionName:       regionName,
		InstanceTypeName: instanceTypeName,
		SSHKeyNames:      []string{sshKeyName},
		Quantity:         1,
	}
	jsonPayload, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	req, err := http.NewRequest("POST", baseUrl+"instance-operations/launch", bytes.NewBuffer(jsonPayload))
	if err != nil {
		return nil, err
	}

	req.SetBasicAuth(apiKey, "")
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result interface{}
	err = json.NewDecoder(resp.Body).Decode(&result)
	if err != nil {
		return nil, err
	}

	return result, nil
}

func launchInstanceLoop() {
	for {
		log.Println("========================================")
		instanceTypes, err := getInstanceTypes()
		if err != nil {
			log.Printf("Error fetching instance types: %v. Retrying in %d seconds.\n", err, errorWait)
			healthStatus = HealthStatus{Status: "error", Error: err.Error()}
			time.Sleep(time.Duration(errorWait) * time.Second)
			continue
		}

		regionName, err := checkInstanceAvailability(instanceTypes)
		if err != nil {
			log.Printf("Error checking instance availability: %v. Retrying in %d seconds.\n", err, errorWait)
			healthStatus = HealthStatus{Status: "error", Error: err.Error()}
			time.Sleep(time.Duration(errorWait) * time.Second)
			continue
		}

		if regionName != "" {
			result, err := launchInstance(regionName)
			if err != nil {
				log.Printf("Error launching instance: %v. Retrying in %d seconds.\n", err, errorWait)
				healthStatus = HealthStatus{Status: "error", Error: err.Error()}
				time.Sleep(time.Duration(errorWait) * time.Second)
				continue
			}

			log.Printf("Instance launch result: %v\n", result)
			healthStatus = HealthStatus{Status: "instance launched", Result: result}
			break
		} else {
			log.Printf("No available regions found for %s. Checking again in %d seconds.\n", instanceTypeName, checkInterval)
		}

		time.Sleep(time.Duration(checkInterval) * time.Second)
	}
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(healthStatus)
}

func main() {
	log.Println("Starting instance launcher script...")
	healthStatus = HealthStatus{Status: "running"}

	go launchInstanceLoop()

	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Get("/health", healthHandler)

	log.Printf("Listening on port %d\n", port)
	log.Fatal(http.ListenAndServe("0.0.0.0:"+strconv.Itoa(port), r))
}
