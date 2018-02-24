/*global module:false*/
module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    // Project settings
    config: {
      dist: 'dist', // Dist path
      dev: 'dev',    // dev path
      // Source elements path
      src: {
        html: 'src/html/**/*.html',
        sass: 'src/css/uds.scss', 
        sass_watch: 'src/css/**/*.scss', 
        typescript: 'src/js/**/*.ts'
      }
      
    },

    // Tasks
    clean: {
      dev: ['<%= config.dev %>'],
      dist: ['<%= config.dist %>'],
    },

    copy: {
      dev: {
        files: [
          { 
            expand: true, 
            flatten: true, 
            src: [
              'node_modules/bootstrap/dist/js/bootstrap.js',  // Bootstrap js
              'node_modules/jquery/dist/jquery.js',  // Jquery js
              'node_modules/popper.js/dist/popper.js' // Popper js
            ], 
            dest: '<%= config.dev %>/js/lib' 
          },  // To Lib folder
          // HTML for testing
          { expand: true, flatten: true, src: ['<%= config.src.html %>'], dest:'<%= config.dev %>' }
        ]
      },
      dist: {
        files: [
          { 
            expand: true, 
            flatten: true, 
            src: [
              'node_modules/bootstrap/dist/js/bootstrap.min.js',  // Bootstrap js
              'node_modules/jquery/dist/jquery.min.js',  // Jquery js
              'node_modules/popper.js/dist/popper.min.js' // Popper js
            ], 
            dest: '<%= config.dist %>/js/lib' 
          }/*,  // To Lib folder
          { expand: true, flatten: true, src: ['<%= config.src.html %>'], dest:'<%= config.dist %>' } */
        ]
      }
    },

    typescript: {
      options: {
        target: 'es3',
      },
      dev: {
        options: {
          sourceMap: true,
        },
          src: [ '<%= config.src.typescript %>' ],
        dest: '<%= config.dev %>/js/uds.js',
      },
      dist: {
        options: {
          sourceMap: false,
        },
          src: [ '<%= config.src.typescript %>' ],
        dest: '<%= config.dist %>/js/uds.js',
      }
      
    },
    // Compiles Sass to CSS and generates necessary files if requested
    sass: {
      options: {
        trace: true,
        loadPath: [
          'node_modules/'
        ],
    },
      dev: {
        options: {
          update: true,
        },
        files: [{
          '<%= config.dev %>/css/uds.css': ['<%= config.src.sass %>']
        }]
      },
      dist: {
        options: {
          update: false,
          style: 'compressed'
        },
        files: [{
          '<%= config.dist %>/css/uds.css': ['<%= config.src.sass %>'],
        }]
      }
    },

    watch: {
      typescript: {
        files: '<%= config.src.typescript %>',
        tasks: ['typescrypt:dev']
      },
      sass: {
        files: '<%= config.src.sass_watch %>',
        tasks: ['sass:dev']
      },
      html: {
        files: '<%= config.src.html %>',
        tasks: ['copy:dev']
      }
    },
    'http-server': {
      dev: {
        root: '<%= config.dev %>',
        port: 9000,
        host: '0.0.0.0',
        cache: 0
      }
    }
  
  });

  // These plugins provide necessary tasks.
  grunt.loadNpmTasks('grunt-contrib-sass');
  grunt.loadNpmTasks('grunt-contrib-copy');
  grunt.loadNpmTasks('grunt-contrib-clean');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-http-server');
  grunt.loadNpmTasks('grunt-typescript');

  // Default task.
  grunt.registerTask('dev', ['copy:dev', 'typescript:dev', 'sass:dev'])
  grunt.registerTask('dist', ['clean:dist', 'copy:dist', 'typescript:dist', 'sass:dist'])
  grunt.registerTask('default', ['dev']);

};
