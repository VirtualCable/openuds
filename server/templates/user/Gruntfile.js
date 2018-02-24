/*global module:false*/

config = {
  dist: 'dist', // Dist path
  dev: 'dev',    // dev path
  uds_template: 'modern',
  // Source elements path
  src: {
    base: 'src',
    html: 'src/*.html',
    templates: 'src/templates/*.html',
    images: ['src/img/**/*.png', 'src/img/**/*.ico', 'src/img/**/*.gif'],
    static: 'src/static',
    server_provided: 'src/server_provided/*',
    sass: 'src/css/uds.scss', 
    sass_watch: 'src/css/**/*.scss', 
    coffee: 'src/js/**/*.coffee',
    js_lib: [
      'node_modules/bootstrap/dist/js/bootstrap.min.js',  // Bootstrap js
      'node_modules/jquery/dist/jquery.min.js',  // Jquery js
      'node_modules/popper.js/dist/umd/popper.min.js', // Popper js
      'node_modules/angular/angular.min.js', // Angular
    ]
  }
  
}


module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    // Project settings
    config: config,

    // Tasks
    clean: {
      dev: ['<%= config.dev %>'],
      dist: ['<%= config.dist %>'],
    },

    copy: {
      dev: {
        files: [
          // Javascript from libs
          { 
            expand: true, 
            flatten: true, 
            src: config.src.js_lib, 
            dest: '<%= config.dev %>/_static_/js/lib' 
          },  
          // Fontawewsome
          { expand: true, flatten: true, src: 'node_modules/font-awesome/fonts/*', dest:'<%= config.dev %>/_static_/fonts' },
          // Index & Templates, no changes for development environment
          { expand: true, flatten: true, src: config.src.html, dest:'<%= config.dev %>' },
          { expand: true, flatten: true, src: config.src.templates, dest:'<%= config.dev %>/_static_/templates' },
          // Images
          { expand: true, flatten: true, src: config.src.images, dest:'<%= config.dev %>/_static_/img' },
          // Other Static elements, from libraries normally
          { expand: true, flatten: false, cwd: config.src.static, src: '**/*', dest:'<%= config.dev %>/_static_/' },
          // Server provided files, so we can "emulate" on development
          { expand: true, flatten: true, src: config.src.server_provided, dest: config.dev },

        ]
      },
      dist: {
        options: {
          // Process files to make them
          process: function(content, srcPath) {
            if( /.?src\/[^\/]*.html/g.test(srcPath) ) {
              grunt.log.write(' converting for template... ');
              return '{% load l10n i18n static%}' + 
                content.replace(/_static_\//g, '{% get_static_prefix %}');
            } else {
              return content;
            }
          }
        },
        files: [
          { 
            expand: true, 
            flatten: true, 
            src: config.src.js_lib, 
            dest: '<%= config.dist %>/static/js/lib' 
          },
          // html files
          { 
            expand: true, 
            flatten: true, 
            src: config.src.html, 
            dest:'<%= config.dist %>/templates/uds/<%= config.uds_template %>',
          },
          // Templates (angular, for now goes to static, but maybe it needs to go to other "django templates" folder)
          { expand: true, flatten: true, src: config.src.templates, dest:'<%= config.dist %>/static/templates' },
          /// Images
          { expand: true, flatten: true, src: config.src.images, dest:'<%= config.dist %>/static/img' },
          // Other Static elements, from libraries normally
          { expand: true, flatten: false, cwd: config.src.static, src: '**/*', dest:'<%= config.dist %>/static/' },
          
          
        ]
      }
    },

    coffee: {
      options: {
        join: true,
      },
      dev: {
        options: {
          sourceMap: true,
        },
        files: {
          '<%= config.dev %>/_static_/js/uds.js': ['<%= config.src.coffee %>']
        },
      },
      dist: {
        options: {
          sourceMap: false,
        },
        files: {
          '<%= config.dist %>/static/js/uds.js': ['<%= config.src.coffee %>']
        },
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
          '<%= config.dev %>/_static_/css/uds.css': ['<%= config.src.sass %>']
        }]
      },
      dist: {
        options: {
          update: false,
          sourcemap: 'none',
          style: 'compressed'
        },
        files: [{
          '<%= config.dist %>/static/css/uds.css': ['<%= config.src.sass %>'],
        }]
      }
    },

    watch: {
      coffee: {
        files: '<%= config.src.coffee %>',
        tasks: ['coffee:dev']
      },
      sass: {
        files: '<%= config.src.sass_watch %>',
        tasks: ['sass:dev']
      },
      html: {
        files: ['<%= config.src.html %>', '<%= config.src.templates %>', '<%= config.src.server_provided %>'],
        tasks: ['copy:dev']
      }
    },
    'http-server': {
      dev: {
        root: '<%= config.dev %>',
        port: 9000,
        host: '0.0.0.0',
        cache: 0,
        runInBackground: true
      }
    }
  
  });

  // These plugins provide necessary tasks.
  grunt.loadNpmTasks('grunt-contrib-sass');
  grunt.loadNpmTasks('grunt-contrib-copy');
  grunt.loadNpmTasks('grunt-contrib-clean');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-http-server');
  grunt.loadNpmTasks('grunt-contrib-coffee');

  // Tasks
  grunt.registerTask('build-dev', ['copy:dev', 'coffee:dev', 'sass:dev'])
  grunt.registerTask('dev', ['build-dev', 'http-server', 'watch'])
  grunt.registerTask('dist', ['clean:dist', 'copy:dist', 'coffee:dist', 'sass:dist'])

  // Default task is dev
  grunt.registerTask('default', ['dist']);

  // Aliases
  grunt.registerTask('serve', ['http-server']);

};
