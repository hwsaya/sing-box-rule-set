package main

import (
	"encoding/csv"
	"io"
	"log"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
)

var (
	inputDir  string
	outputDir string
)

var convertCmd = &cobra.Command{
	Use:   "convert",
	Short: "Convert GeoLite2 CSV to CIDR text files",
	RunE: func(cmd *cobra.Command, args []string) error {
		return runConvert()
	},
}

var rootCmd = &cobra.Command{
	Use:   "geoip",
	Short: "geoip tool",
}

func init() {
	rootCmd.AddCommand(convertCmd)
	convertCmd.Flags().StringVarP(&inputDir, "input", "i", "geolite2", "input directory")
	convertCmd.Flags().StringVarP(&outputDir, "output", "o", "output/text", "output directory")
}

func runConvert() error {
	os.MkdirAll(outputDir, 0755)

	locations, err := loadLocations(filepath.Join(inputDir, "GeoLite2-Country-Locations-en.csv"))
	if err != nil {
		return err
	}

	for _, filename := range []string{"GeoLite2-Country-Blocks-IPv4.csv", "GeoLite2-Country-Blocks-IPv6.csv"} {
		if err := processBlocks(filepath.Join(inputDir, filename), locations); err != nil {
			log.Printf("Warning: failed to process %s: %v", filename, err)
		}
	}
	return nil
}

func loadLocations(path string) (map[string]bool, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	cnIds := make(map[string]bool)
	r := csv.NewReader(f)
	r.Read()
	for {
		record, err := r.Read()
		if err == io.EOF {
			break
		}
		if len(record) > 4 && record[4] == "CN" {
			cnIds[record[0]] = true
		}
	}
	return cnIds, nil
}

func processBlocks(path string, cnIds map[string]bool) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	out, err := os.Create(filepath.Join(outputDir, filepath.Base(path)+".txt"))
	if err != nil {
		return err
	}
	defer out.Close()

	r := csv.NewReader(f)
	r.Read()
	for {
		record, err := r.Read()
		if err == io.EOF {
			break
		}
		isCN := cnIds[record[1]] || cnIds[record[2]]
		if !isCN && len(record) > 0 {
			out.WriteString(record[0] + "\n")
		}
	}
	return nil
}

func main() {
	if err := rootCmd.Execute(); err != nil {
		log.Fatal(err)
	}
}
