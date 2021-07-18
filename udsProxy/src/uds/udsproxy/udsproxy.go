package main

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"io/ioutil"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"time"

	ini "gopkg.in/ini.v1"
)

const configFilename = "/etc/udsproxy.cfg"

var config struct {
	Server                string   // Server Type, "http" or "https"
	Port                  string   // Server port
	SSLCertificateFile    string   // Certificate file
	SSLCertificateKeyFile string   // Certificate key
	Broker                string   // Broker address
	AllowFrom             []string // Allow BROKER requests from this IPS
	UseSSL                bool     // If use https for connecting with broker: Warning, certificate must be valid on Broker
	IgnoreCertificates    bool     // If true, will ignore certificates (when requesting)
}

func validateOrigin(w http.ResponseWriter, r *http.Request) error {
	ip := strings.Split(r.RemoteAddr, ":")[0]
	for _, v := range config.AllowFrom {
		if v == ip {
			return nil
		}
	}
	w.WriteHeader(http.StatusForbidden)
	fmt.Fprintf(w, "Access denied")
	return errors.New("Invalid Origin")
}

// Test service
func testService(w http.ResponseWriter, r *http.Request) {
	if validateOrigin(w, r) != nil {
		return
	}

	r.ParseForm()
	host, port, timeOutStr := r.FormValue("host"), r.FormValue("port"), r.FormValue("timeout")
	if host == "" || port == "" {
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "Invalid arguments")
		return
	}
	if timeOutStr == "" {
		timeOutStr = "4"
	}

	timeOut, _ := strconv.Atoi(timeOutStr)

	fmt.Println("Args: ", host, port)
	con, err := net.DialTimeout("tcp", host+":"+port, time.Duration(timeOut)*time.Second)

	if err == nil {
		con.Close()
		w.WriteHeader(http.StatusFound)
		fmt.Fprint(w, "ok")
	} else {
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprint(w, err)
	}
}

func proxyRequest(w http.ResponseWriter, r *http.Request) {
	if validateOrigin(w, r) != nil {
		return
	}
	log.Print("Proxy Request from ", r.RemoteAddr)
	// Content is always a POST, and we have json on request body
	// If recovered json contains "data", then we must produce a POST to service
	// url to request is on "url" json variable
	var body struct {
		Data json.RawMessage
		URL  string
	}

	dec := json.NewDecoder(r.Body)

	if err := dec.Decode(&body); err != nil {
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "Error in Json: %s", err)
		log.Printf("Error decoding json: %s", err)
		return
	}

	var method string
	if body.Data != nil {
		log.Print("POSTING request to ", body.URL)
		method = "POST"
	} else {
		log.Print("GETTING request from ", body.URL)
		method = "GET"
	}

	req, err := http.NewRequest(method, body.URL, bytes.NewBuffer(body.Data))

	if err != nil {
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "Error building request: %s", err)
		log.Printf("Error building request: %s", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	// Ignore Certificate
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: config.IgnoreCertificates},
	}

	client := &http.Client{
		Timeout:   time.Duration(5) * time.Second,
		Transport: tr,
	}

	resp, err := client.Do(req)

	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		log.Printf("The connection failed %s", err)
		fmt.Fprintf(w, "Error in POST: %s", err)
		return
	}

	defer resp.Body.Close() // Ensures closes response
	w.WriteHeader(resp.StatusCode)
	b, _ := ioutil.ReadAll(resp.Body)

	log.Printf("Response: %d, %s", resp.StatusCode, b)

	w.Write(b)
}

func actor(w http.ResponseWriter, r *http.Request) {
	// Get Request as received and forward it to UDS, without changing anything...
	// We will net params, body, etc...
	// Currently not implemented/finished

	r.ParseForm()       // parse arguments, you have to call this by yourself
	fmt.Println(r.Form) // print form information in server side
	fmt.Println("path", r.URL.Path)
	fmt.Println("scheme", r.URL.Scheme)
	fmt.Println(r.Form["url_long"])
	for k, v := range r.Form {
		fmt.Println("key:", k)
		fmt.Println("val:", strings.Join(v, ""))
	}
	fmt.Fprintf(w, "Hello astaxie!") // send data to client side
}

func main() {

	cfg, err := ini.Load(configFilename)
	if err != nil {
		log.Fatal(err) // Fatal calss exit
	}
	// Default config values
	config.Port = "9090"

	// Read config
	cfg.MapTo(&config)

	log.Printf("Broker: %s", config.Broker)
	log.Printf("Server type: %s", config.Server)
	log.Printf("Server port: %s", config.Port)
	log.Printf("Allow Access from: %s", config.AllowFrom)

	// Handle signals
	// we make a buffered channel to do not loose signal
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, os.Kill)
	go func() {
		for range c {
			fmt.Print("Got Ending signal")
			os.Exit(0)
		}
	}()

	http.HandleFunc("/actor", actor)               // set router for "actor" requests
	http.HandleFunc("/testServer", testService)    // test service
	http.HandleFunc("/proxyRequest", proxyRequest) // Proxy request from broker to service

	if config.Server == "https" {
		err = http.ListenAndServeTLS(":"+config.Port, config.SSLCertificateFile, config.SSLCertificateKeyFile, nil) // set listen port
	} else {
		err = http.ListenAndServe(":"+config.Port, nil) // set listen port
	}

	if err != nil {
		log.Fatal("ListenAndServe: ", err) // Fatal calls exit
	}

}
