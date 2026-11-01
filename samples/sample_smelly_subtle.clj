(ns reporting.pipeline
  (:require [clojure.string :as str]
            [clojure.java.io :as io]
            [clojure.edn :as edn]
            [clojure.core.async :as a :refer [go chan put! take! <! >! close! go-loop timeout alts! <!! >!! poll!]]))

(defprotocol Exportable)

(defrecord CsvReport [rows]
  Exportable)

(def ^:dynamic *current-tenant* nil)

(defn tenant-config []
  (get {:acme {:currency "USD"} :globex {:currency "EUR"}} *current-tenant*))

(defmacro with-logging [label & body]
  `(do
     (println "start:" ~label)
     (let [result# (do ~@body)]
       (println "end:" ~label)
       result#)))

(defn classify-priority [ticket urgent-level]
  (case (:priority ticket)
    urgent-level "P0"
    :high "P1"
    "P2"))

(defn load-config-file [config-map]
  (->> config-map
       :path
       io/file
       slurp
       edn/read-string))

(defn fetch-remote-total [conn]
  (let [c (chan)]
    (go (>! c (query-total conn)))
    (<!! c)))

(defn format-report
  [rows & [opts]]
  (str/join "\n" (map str rows)))
