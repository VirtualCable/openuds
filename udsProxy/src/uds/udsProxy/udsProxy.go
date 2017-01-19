package main

import (
	"fmt"
	"log"
	"net"
	"net/http"
	"strconv"
	"strings"
	"time"

	ini "gopkg.in/ini.v1"
)

const configFilename = "/etc/UDSProxy.cfg"

var config struct {
	Broker string `ini:"broker"` // Broker address
}

// Test service
func testService(w http.ResponseWriter, r *http.Request) {
	if strings.Split(r.RemoteAddr, ":")[0] != config.Broker {
		w.WriteHeader(http.StatusForbidden)
		fmt.Fprintf(w, "Access denied")
	}
	r.ParseForm()
	ip, port, timeOutStr := r.FormValue("ip"), r.FormValue("port"), r.FormValue("timeout")
	if ip == "" || port == "" {
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "Invalid arguments")
		return
	}
	if timeOutStr == "" {
		timeOutStr = "4"
	}

	timeOut, _ := strconv.Atoi(timeOutStr)

	fmt.Println("Args: ", ip, port)
	con, err := net.DialTimeout("tcp", ip+":"+port, time.Duration(timeOut)*time.Second)

	if err == nil {
		con.Close()
		w.WriteHeader(http.StatusFound)
		fmt.Fprint(w, "ok")
	} else {
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprint(w, err)
	}
}

func actor(w http.ResponseWriter, r *http.Request) {
	// Get Request as received and forward it to UDS, withouch changing anything...
	// We will net params, body, etc...

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
		log.Fatal(err)
	}
	cfg.MapTo(&config)

	fmt.Println("Broker address: ", config.Broker)
	http.HandleFunc("/actor", actor) // set router
	http.HandleFunc("/testService", testService)
	err = http.ListenAndServe(":9090", nil) // set listen port
	if err != nil {
		log.Fatal("ListenAndServe: ", err)
	}
}
